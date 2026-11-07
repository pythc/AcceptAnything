"""Conservative source-bound service graph; no repository names or host services."""
import ast,json,re,shlex,time
from datetime import datetime,timezone
from pathlib import Path
from urllib.parse import urlsplit
from ..integrations.runner import encode,sha
from ..integrations.formats import require

CATALOG={'redis':dict(image='universal-redis',port=6379,command=['redis-server','--save','','--appendonly','no'],probe=['redis-cli','ping']),
         'postgresql':dict(image='universal-postgres',port=5432,command=[],probe=['pg_isready','-U','acceptance']),
         'mongodb':dict(image='universal-mongo',port=27017,command=['mongod','--bind_ip','127.0.0.1'],probe=['mongosh','--quiet','--eval','db.adminCommand({ping:1}).ok'])}


def discover(root,files,units,owner):
    from html.parser import HTMLParser
    class Elements(HTMLParser):
        def __init__(self):super().__init__();self.rows=[]
        def handle_starttag(self,tag,attrs):
            attrs=dict(attrs)
            # Result regions are as important as controls for a browser journey.
            # Index locators only: observed page text must not become an oracle.
            if tag in {'input','button','form','textarea','select','a','output'} or any(attrs.get(k) for k in ('id','data-testid','role')):
                self.rows.append(dict(tag=tag,attributes={k:v for k,v in attrs.items() if k in {'id','data-testid','role','aria-label','name','type','method','action','href','required','min','max'}}))
    for u in units:
        nodes={};ui=[]
        for name in files:
            if owner(name,u['runtime'])!=u:continue
            relative=Path(name).relative_to(u['path'])
            if set(relative.parts)&{'tests','test','fixtures','testdata','node_modules','benchmarks'}:continue
            text=(root/name).read_text(errors='replace') if Path(name).suffix in {'.py','.js','.ts','.json','.toml','.yaml','.yml','.md','.rst','.html'} else ''
            if not text:continue
            source=dict(path=name,sha256=sha((root/name).read_bytes()))
            if name.endswith('.html'):
                parser=Elements();parser.feed(text)
                if parser.rows:ui.append(dict(**source,elements=parser.rows))
            # Only source/config literals declare endpoints. Docs provide launch
            # commands, not permission to contact a public or production URI.
            if Path(name).suffix in {'.py','.js','.ts','.json','.toml','.yaml','.yml'}:
                literals=[]
                if name.endswith('.py'):
                    try:literals=[(n.value,n.lineno) for n in ast.walk(ast.parse(text)) if isinstance(n,ast.Constant) and isinstance(n.value,str)]
                    except SyntaxError:pass
                else:literals=[(m.group(1),text[:m.start()].count('\n')+1) for m in re.finditer(r'["\']((?:redis|postgresql|postgres|mongodb)://[^"\'\s]+)["\']',text)]
                for value,line in literals:
                    if not re.match(r'^(redis|postgresql|postgres|mongodb)://',value):continue
                    try:uri=urlsplit(value);kind={'postgres':'postgresql'}.get(uri.scheme,uri.scheme);port=uri.port or CATALOG[kind]['port']
                    except (ValueError,KeyError):continue
                    if uri.hostname not in {'localhost','127.0.0.1','::1'}:continue
                    key=kind+'-'+str(port);spec=CATALOG[kind]
                    # Non-default/authenticated services require an explicit
                    # credential/port contract; never rewrite source defaults.
                    supported=port==spec['port'] and not (uri.username or uri.password) and kind=='redis'
                    node=nodes.setdefault(key,dict(id=key,kind=kind,needs=[],supported=supported,port=port,sources=[]))
                    node['sources'].append(dict(**source,line=line,locator=kind+'://loopback:'+str(port)))
            if Path(name).suffix in {'.md','.rst'}:
                for line_number,line in enumerate(text.splitlines(),1):
                    cmd=line.strip().removeprefix('$ ').strip()
                    if not cmd.startswith('celery '):continue
                    if re.search(r'[;&|`$<>\\]',cmd):continue
                    try:argv=shlex.split(cmd)
                    except ValueError:continue
                    if 'worker' not in argv or '-A' not in argv:continue
                    try:module=argv[argv.index('-A')+1]
                    except IndexError:continue
                    if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_.]*(?::[A-Za-z][A-Za-z0-9_]*)?',module):continue
                    module_path=module.split(':')[0].replace('.','/')
                    if not any((root/u['path']/p).is_file() for p in (module_path+'.py',module_path+'/__init__.py','src/'+module_path+'.py','src/'+module_path+'/__init__.py')):continue
                    key='worker-'+sha(encode(argv))[:10]
                    nodes[key]=dict(id=key,kind='celery',argv=argv,needs=[],supported=True,sources=[dict(**source,line=line_number,command=cmd)])
        endpoints=[n['id'] for n in nodes.values() if n['kind']!='celery']
        for node in nodes.values():
            if node['kind']=='celery':node['needs']=endpoints
        ordered=[];pending=list(nodes.values())
        while pending:
            available={n['id'] for n in ordered};ready=[n for n in pending if set(n['needs'])<=available]
            if not ready:raise ValueError('服务依赖图存在循环')
            for n in ready:ordered.append(n);pending.remove(n)
        u['service_graph']=dict(version=1,nodes=ordered)
        u['ui_bindings']=ui
        if u['runtime'] in {'python','node'} and u.get('interfaces'):u['capabilities'].append('journey')


def start(run,u,output,cancelled,on_progress=None):
    from .runtime import docker,names,env_path,command
    from .fixture_preparation import options as fixture_options
    name,volume=names(run,u);records=[];states={};graph=u.get('service_graph',{}).get('nodes',[])
    run.setdefault('universal_graphs',{})[u['id']]=records
    for node in graph:
        target=output/node['id'];target.mkdir();begin=time.monotonic();record={**node,'status':'preparing','started_at':datetime.now(timezone.utc).isoformat()};records.append(record);probes=[]
        cname=name+'-'+node['id'];record['container']=cname
        if on_progress:on_progress()
        try:
            require(not cancelled(),'多服务准备已取消')
            require(node['supported'],'服务声明需要额外连接/凭据契约，未猜测配置')
            require(all(states.get(n)=='ready' for n in node['needs']),'依赖服务未就绪：'+', '.join(node['needs']))
            argv=['run','-d','--name',cname,'--label','acceptance.integration=true','--label','acceptance.run='+run['id'],'--network','container:'+name,'--cap-drop','ALL','--security-opt','no-new-privileges','--pids-limit','256','--cpus','2','--tmpfs','/tmp:rw,exec,nosuid']
            if node['kind']=='celery':
                argv+=fixture_options(run)
                image=json.loads(docker('inspect',name).stdout)[0]['Image']
                record['argv']=[*node['argv'],'--pool=solo','--concurrency=1','--hostname=acceptance@'+u['id']]
                # Pool/concurrency are execution resources, never eager mode.
                argv+=['--read-only','--env','HOME=/work','--env','C_FORCE_ROOT=1','-w','/work/repo/'+u['path'],'--mount',f'type=volume,src={volume},dst=/work','--entrypoint','/work/venv/bin/celery',image,*record['argv'][1:]]
                docker(*argv)
                probe=['/work/venv/bin/celery','-A',node['argv'][node['argv'].index('-A')+1],'inspect','ping','--destination','acceptance@'+u['id'],'--timeout','1','--json']
            else:
                spec=CATALOG[node['kind']];require(spec['image'] in run['images'],'服务镜像未安装或未锁定：'+spec['image'])
                image=run['images'][spec['image']]['id'];docker(*argv,image,*spec['command']);probe=spec['probe']
            record['image']=image
            deadline=time.monotonic()+45
            probes=[]
            while time.monotonic()<deadline:
                require(not cancelled(),'多服务准备已取消')
                if node['kind']=='celery':
                    p=docker('exec','-w','/work/repo/'+u['path'],cname,*probe,check=False)
                    try:healthy=p.returncode==0 and json.loads(p.stdout).get('acceptance@'+u['id'],{}).get('ok')=='pong'
                    except (ValueError,AttributeError):healthy=False
                else:
                    p=docker('exec',cname,*probe,check=False);healthy=p.returncode==0 and p.stdout.strip()=='PONG'
                probes.append(dict(argv=probe,exit_code=p.returncode,stdout=p.stdout,stderr=p.stderr))
                if healthy:break
                inspect=json.loads(docker('inspect',cname).stdout)[0]
                require(inspect['State']['Running'],'服务进程已退出');time.sleep(.2)
            else:raise ValueError('服务未在准备预算内就绪')
            record.update(status='ready',probes=probes)
        except Exception as exc:record.update(status='error',error=str(exc),probes=probes)
        finally:
            state=docker('inspect',cname,check=False);log=docker('logs',cname,check=False)
            (target/'inspect.json').write_text(state.stdout);(target/'service.log').write_text(log.stdout+log.stderr)
            record['duration_ms']=round((time.monotonic()-begin)*1000);states[node['id']]=record['status']
            (output/'graph.json').write_bytes(encode(records))
            if on_progress:on_progress()
    return records


def cleanup(run,u,output):
    from .runtime import docker,names
    name,_=names(run,u);records=[]
    for node in reversed(u.get('service_graph',{}).get('nodes',[])):
        cname=name+'-'+node['id'];log=docker('logs',cname,check=False)
        (output/(node['id']+'.log')).write_text(log.stdout+log.stderr)
        docker('rm','-f',cname,check=False)
        records.append(dict(id=node['id'],removed=docker('inspect',cname,check=False).returncode!=0))
    return records
