"""Static manifests and AST index. No imports or project commands on the host."""
import ast
import json
from pathlib import Path
import re
import subprocess
import tomllib
from ..integrations.runner import sha,encode
from ..integrations.registry import ROOT
from ..planning.basis import candidate_order

NOISE={'tests','test','testdata','fixtures','examples','benchmarks','benchmark','scripts','docs'}


def link_local_commands(units,gaps):
    """Reuse commands declared by packages installed into the same environment."""
    by_id={u['id']:u for u in units}
    declared={u['id']:dict(u.get('cli_commands',{})) for u in units}
    for u in units:
        if u['runtime']!='python':continue
        candidates={}
        for owner_id in dict.fromkeys([u['id'],*u.get('local_dependencies',[])]):
            owner=by_id[owner_id]
            if owner['runtime']!='python':continue
            for name,argv in declared[owner_id].items():
                candidates.setdefault(name,[]).append(dict(unit=owner_id,manifest=owner['manifest'],argv=argv))
        commands={};origins={}
        for name,owners in candidates.items():
            if len(owners)!=1:
                gaps.append(dict(kind='entry',source=u['manifest'],reason='本地依赖声明了冲突的 CLI 名称 '+name+'；未猜测安装后的入口归属'))
                continue
            commands[name]=owners[0]['argv'];origins[name]=owners[0]
        u['cli_commands']=commands;u['cli_origins']=origins
        u['capabilities']=[c for c in u['capabilities'] if c!='cli']+(['cli'] if commands else [])


def rank(path):
    p=Path(path)
    return (bool(set(p.parts)&NOISE),p.name not in {'__init__.py','index.js','index.ts','index.mjs'},len(p.parts),path)


def python_exports(root,name,seen=None,_cache=None):
    seen=set(seen or ())
    if name in seen:return []
    # Cache only within this discovery, including the recursion ancestry so
    # cyclic imports retain their original semantics. Never reuse across roots
    # or revisions. Repeated individual reexports must not reparse a large SDK.
    cache={} if _cache is None else _cache
    key=(name,frozenset(seen))
    if key in cache:return cache[key]
    seen.add(name)
    try:tree=ast.parse((root/name).read_text())
    except (SyntaxError,UnicodeError):return []
    rows=[];explicit=None
    for node in tree.body:
        if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='__all__' for t in node.targets):
            try:explicit=set(ast.literal_eval(node.value))
            except (ValueError,TypeError):pass
        if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)):
            args=node.args;defaults=[False]*(len(args.posonlyargs)+len(args.args)-len(args.defaults))+[True]*len(args.defaults)
            rows.append(dict(name=node.name,async_function=isinstance(node,ast.AsyncFunctionDef),parameters=[dict(name=a.arg,optional=d,type=ast.unparse(a.annotation) if a.annotation else None) for a,d in zip([*args.posonlyargs,*args.args],defaults)],
                keyword_only=[dict(name=a.arg,optional=d is not None) for a,d in zip(args.kwonlyargs,args.kw_defaults)],variadic=bool(args.vararg or args.kwarg),return_type=ast.unparse(node.returns) if node.returns else None))
        if isinstance(node,ast.ClassDef):
            methods=[]
            for m in node.body:
                if not isinstance(m,(ast.FunctionDef,ast.AsyncFunctionDef)) or m.name.startswith('_') and m.name!='__init__':continue
                decorators={d.id if isinstance(d,ast.Name) else d.attr if isinstance(d,ast.Attribute) else '' for d in m.decorator_list}
                methods.append(dict(name=m.name,kind='property' if decorators&{'property','cached_property'} else 'method',
                    parameters=[a.arg for a in [*m.args.posonlyargs,*m.args.args] if a.arg not in {'self','cls'}],
                    variadic=bool(m.args.vararg or m.args.kwarg),varargs=m.args.vararg.arg if m.args.vararg else None,varkwargs=m.args.kwarg.arg if m.args.kwarg else None,
                    keyword_only=[dict(name=a.arg,optional=d is not None) for a,d in zip(m.args.kwonlyargs,m.args.kw_defaults)],
                    return_type=ast.unparse(m.returns) if m.returns else None,async_function=isinstance(m,ast.AsyncFunctionDef)))
            rows.append(dict(name=node.name,kind='class',methods=methods,bases=[ast.unparse(b) for b in node.bases]))
        if isinstance(node,ast.ImportFrom) and node.level:
            parent=Path(name).parent
            for _ in range(node.level-1):parent=parent.parent
            target=parent/((node.module or '').replace('.','/'))
            candidates=[target.with_suffix('.py'),target/'__init__.py']
            resolved=next((str(p) for p in candidates if (root/p).is_file()),None)
            if resolved:
                exports={r['name']:r for r in python_exports(root,resolved,seen,cache)}
                for alias in node.names:
                    if alias.name in exports:rows.append({**exports[alias.name],'name':alias.asname or alias.name,'reexport':resolved})
    result=[r for r in rows if r['name'] in explicit] if explicit is not None else [r for r in rows if not r['name'].startswith('_')]
    cache[key]=result
    return result


def discover(root,files):
    units=[];gaps=[];interfaces=[];types=[]
    def unit(runtime,manifest,settings):
        path=str(Path(manifest).parent);uid='u-'+sha((runtime+':'+path).encode())[:10]
        units.append(dict(id=uid,runtime=runtime,path=path,manifest=manifest,settings=settings,capabilities=['module','scenario'] if runtime in {'python','node'} else ['cli']))
    for name in files:
        p=Path(name)
        if set(p.parts[:-1])&{'testdata','fixtures','vendor','node_modules'}:continue
        if set(p.parts[:-1])&NOISE and p.name not in {'package.json','pyproject.toml'}:continue
        try:
            if p.name=='package.json':
                settings=json.loads((root/name).read_text())
                if set(p.parts[:-1])&NOISE and not (settings.get('scripts',{}).keys() & {'test','build','start'}):continue
                unit('node',name,settings)
            elif p.name=='pyproject.toml':
                settings=tomllib.loads((root/name).read_text())
                if set(p.parts[:-1])&NOISE and not (settings.get('project',{}).get('name') and settings.get('build-system')):continue
                unit('python',name,settings)
            elif p.name in {'setup.py','setup.cfg','requirements.txt'} and not any(u['runtime']=='python' and u['path']==str(p.parent) for u in units):unit('python',name,{})
            elif p.name=='go.mod':unit('go',name,{'module':(root/name).read_text()})
            elif p.name=='Cargo.toml':
                settings=tomllib.loads((root/name).read_text())
                if not any(u['runtime']=='rust' and 'workspace' in u['settings'] and (u['path']=='.' or name.startswith(u['path']+'/')) for u in units):unit('rust',name,settings)
            elif p.name in {'pom.xml','build.gradle','composer.json','Gemfile'}:
                gaps.append(dict(kind='adapter',source=name,reason='已识别项目声明；此运行协议的执行器尚未安装，不阻止其他组件检查'))
        except (ValueError,UnicodeError) as exc:gaps.append(dict(kind='manifest',source=name,reason=type(exc).__name__+'：项目声明无法解析'))
    if not units and any(n.endswith('.py') for n in files):unit('python','setup.py',{})
    # Prefer an actual project declaration over an earlier requirements file.
    units=list({(u['runtime'],u['path']):u for u in units}.values())
    def owner(name,runtime):
        options=[u for u in units if u['runtime']==runtime and (u['path']=='.' or name.startswith(u['path']+'/'))]
        return max(options,key=lambda u:len(u['path'])) if options else None
    for name in sorted(files,key=rank):
        if not name.endswith('.py'):continue
        u=owner(name,'python')
        if not u:continue
        exports=python_exports(root,name)
        if exports:interfaces.append(dict(unit=u['id'],path=name,runtime='python',functions=exports,auxiliary=bool(set(Path(name).relative_to(u['path']).parts)&NOISE)))
        if not set(Path(name).relative_to(u['path']).parts)&NOISE:
            try:
                tree=ast.parse((root/name).read_text())
                framework_names={a.asname or a.name:a.name for n in tree.body if isinstance(n,ast.ImportFrom) and n.module in {'flask','fastapi'} for a in n.names if a.name in {'Flask','FastAPI'}}
                for n in tree.body:
                    if isinstance(n,ast.Assign) and isinstance(n.value,ast.Call) and isinstance(n.value.func,ast.Name) and n.value.func.id in framework_names and len(n.targets)==1 and isinstance(n.targets[0],ast.Name):
                        module=str(Path(name).relative_to(u['path'])).removeprefix('src/').removesuffix('.py').removesuffix('/__init__').replace('/','.')
                        u.setdefault('services',[]).append(dict(framework=framework_names[n.value.func.id],module=module,attribute=n.targets[0].id,port=19300))
                    if isinstance(n,ast.FunctionDef) and not n.name.startswith('_') and len(n.args.posonlyargs)+len(n.args.args)<=len(n.args.defaults) and all(v is not None for v in n.args.kw_defaults):
                        created={a.targets[0].id:framework_names[a.value.func.id] for a in n.body if isinstance(a,ast.Assign) and len(a.targets)==1 and isinstance(a.targets[0],ast.Name) and isinstance(a.value,ast.Call) and isinstance(a.value.func,ast.Name) and a.value.func.id in framework_names}
                        returned={a.value.id for a in n.body if isinstance(a,ast.Return) and isinstance(a.value,ast.Name)}
                        if len(returned)==1 and returned<=created.keys():
                            module=str(Path(name).relative_to(u['path'])).removeprefix('src/').removesuffix('.py').removesuffix('/__init__').replace('/','.')
                            u.setdefault('services',[]).append(dict(framework=created[next(iter(returned))],module=module,attribute=n.name,factory=True,port=19300))
            except (SyntaxError,UnicodeError):pass
    js=[dict(path=n,text=(root/n).read_text(errors='replace')) for n in sorted(files,key=rank) if Path(n).suffix in {'.js','.mjs','.cjs','.ts','.tsx','.jsx'} and owner(n,'node')]
    if js:
        from ..engine import NODE
        proc=subprocess.run([str(NODE),str(Path(__file__).with_name('typescript.cjs')),str(ROOT/'web/node_modules/@babel/parser')],input=json.dumps(js),capture_output=True,text=True,timeout=60)
        if proc.returncode:gaps.append(dict(kind='syntax-index',source='JavaScript/TypeScript',reason='语法索引器未完成'))
        else:
            for row in json.loads(proc.stdout):
                u=owner(row['path'],'node');path=row['path']
                if row.get('types'):types.append(dict(unit=u['id'],path=path,types=row['types']))
                if path.endswith('.d.ts'):
                    replacement=path[:-5]+'.js'
                    if replacement in files:path=replacement
                    elif isinstance(u['settings'].get('exports'),str):path=str(Path(u['path'])/u['settings']['exports'])
                if row['exports']:interfaces.append(dict(unit=u['id'],path=path,runtime='node',functions=row['exports'],auxiliary=bool(set(Path(row['path']).relative_to(u['path']).parts)&NOISE)))
    for u in units:
        if u['runtime']=='python':
            settings=u['settings'];build=settings.get('build-system',{})
            u['native_build']=any('maturin' in x or 'setuptools-rust' in x for x in build.get('requires',[]))
            u['test_extra']=next((x for x in ['test','tests','testing','dev'] if x in settings.get('project',{}).get('optional-dependencies',{})),None)
            groups=settings.get('dependency-groups',{})
            def group_deps(name,seen=None):
                seen=set(seen or ())
                if name in seen:return []
                seen.add(name);result=[]
                for row in groups.get(name,[]):
                    if isinstance(row,str):result.append(row)
                    elif isinstance(row,dict) and 'include-group' in row:result+=group_deps(row['include-group'],seen)
                return result
            test_group=next((x for x in ['test','tests','testing'] if x in groups),None)
            if not test_group and any(re.match(r'^(pytest|hypothesis|unittest)',d) for d in group_deps('dev')):test_group='dev'
            u['test_dependencies']=group_deps(test_group) if test_group else []
            u['local_dependencies']=[]
            u['provides']=list({Path(f).relative_to(u['path']).parts[0 if not Path(f).relative_to(u['path']).parts[0]=='src' else 1] for f in files if owner(f,'python')==u and f.endswith('/__init__.py') and not set(Path(f).relative_to(u['path']).parts)&NOISE and len(Path(f).relative_to(u['path']).parts)>1})
        if u['runtime']=='node':
            entry=u['settings'].get('exports') or u['settings'].get('main')
            if isinstance(entry,dict):entry=entry.get('.') or entry
            if isinstance(entry,dict):entry=entry.get('import') or entry.get('default') or entry.get('require')
            if isinstance(entry,dict):entry=entry.get('default')
            if isinstance(entry,str):u['runtime_entry']=str(Path(u['path'])/entry)
        commands={}
        if u['runtime']=='python':
            commands={name:['/work/venv/bin/'+name] for name in u['settings'].get('project',{}).get('scripts',{}) if re.fullmatch(r'[A-Za-z0-9_.-]+',name)}
        elif u['runtime']=='node':
            bins=u['settings'].get('bin',{})
            if isinstance(bins,str):bins={u['settings'].get('name','').split('/')[-1]:bins}
            if isinstance(bins,dict):
                for name,value in bins.items():
                    if isinstance(value,str) and re.fullmatch(r'[A-Za-z0-9_.-]+',name) and not Path(value).is_absolute() and '..' not in Path(value).parts:
                        commands[name]=['node','--import','/opt/acceptance-loader/node_modules/tsx/dist/loader.mjs','/work/repo/'+str(Path(u['path'])/value)]
        u['cli_commands']=commands
        if u['runtime']=='node':
            parents=[v for v in units if v['runtime']=='node' and v['id']!=u['id'] and (v['path']=='.' or u['path'].startswith(v['path']+'/'))]
            u['ancestor_dependencies']=[dict(path=v['path'],manifest=v['manifest']) for v in sorted(parents,key=lambda v:len(v['path']))]
            u['native_commands']=list(u['settings'].get('scripts',{}))
        if commands:u['capabilities']+=['cli']
        prefix='' if u['path']=='.' else u['path']+'/'
        if u['runtime']=='rust':
            manifests=[f for f in files if Path(f).name=='Cargo.toml' and (u['path']=='.' or f.startswith(u['path']+'/'))]
            entries=[]
            for f in manifests:
                data=tomllib.loads((root/f).read_text());package=data.get('package',{})
                if (root/Path(f).parent/'src/main.rs').is_file() and package.get('name'):entries.append(package['name'])
                entries.extend(b['name'] for b in data.get('bin',[]) if b.get('name'))
            u['entries']=list(dict.fromkeys(entries))
            if not u['entries']:u['capabilities']=[]
        if u['runtime']=='go':
            u['entries']=list(dict.fromkeys(str(Path(f).parent.relative_to(u['path'])) for f in files if f.startswith(prefix) and f.endswith('.go') and not f.endswith('_test.go') and not any(p.startswith(('.', '_')) for p in Path(f).parts[:-1]) and re.search(r'(?m)^package main\b',(root/f).read_text(errors='replace'))))
            if not u['entries']:gaps.append(dict(kind='entry',source=u['manifest'],reason='未找到命令行main入口；Go库用例需要模块执行器'))
        u['test_files']=[f for f in files if f.startswith(prefix) and owner(f,u['runtime'])==u and (re.search(r'(^|/)(tests?|testdata)(/|$)|(^|/)test_|_test\.py$|_test\.go$|\.(test|spec)\.[cm]?[jt]s$',f))]
        u['interfaces']=sum(row['unit']==u['id'] for row in interfaces)
        if u['runtime']=='node' and not u['interfaces']:u['capabilities']=[]
        if u['runtime']=='node':u['syntax_files']=[n for n in files if Path(n).suffix in {'.js','.mjs','.cjs'} and owner(n,'node')==u and not set(Path(n).relative_to(u['path']).parts)&NOISE]
        if u['runtime']=='node' and u['settings'].get('scripts',{}).get('start'):
            u['services']=[dict(framework='npm-start',port=19300)]
        if len(u.get('services',[]))==1:u['capabilities']+=['http','browser']
        elif len(u.get('services',[]))>1:gaps.append(dict(kind='service',source=u['manifest'],reason='多个服务声明尚未唯一绑定；模块与扫描仍继续'))
    # Link imports to locally declared Python packages, with no project names.
    for u in units:
        if u['runtime']!='python':continue
        imports=set()
        for f in files:
            if owner(f,'python')!=u or not f.endswith('.py') or set(Path(f).relative_to(u['path']).parts)&NOISE:continue
            try:
                for n in ast.walk(ast.parse((root/f).read_text())):
                    if isinstance(n,ast.ImportFrom) and n.level==0 and n.module:imports.add(n.module.split('.')[0])
                    elif isinstance(n,ast.Import):imports.update(a.name.split('.')[0] for a in n.names)
            except (SyntaxError,UnicodeError):pass
        u['local_dependencies']=[v['id'] for v in units if v['runtime']=='python' and v['id']!=u['id'] and imports&set(v.get('provides',[]))]
    link_local_commands(units,gaps)
    from .orchestration import discover as discover_services
    discover_services(root,files,units,owner)
    from .routes import discover as discover_routes
    discover_routes(root,files,units,owner)
    from .preparation import discover as prepare_environment
    for u in units:
        if u['runtime']=='python':u['environment_preparation']=prepare_environment(root,files,u)
    candidates=[]
    for name in files:
        p=Path(name)
        if p.suffix.lower() not in {'.md','.mkd','.markdown','.rst','.txt','.json','.yaml','.yml'}:continue
        authority=p.stem.lower() in {'readme','prd','requirements','contract','specification','spec','openapi','swagger'}
        if not authority and not name.startswith(('docs/requirements/','docs/specs/')):continue
        # requirements.txt is an installation manifest, not independent behavior.
        if p.name=='requirements.txt':continue
        candidates.append(dict(path=name,category='contract' if p.stem.lower() in {'openapi','swagger','contract','spec','specification','prd','requirements'} else 'overview',characters=len((root/name).read_text(errors='replace')),sha256=sha((root/name).read_bytes())))
    candidates.sort(key=candidate_order)
    from .documents import catalog
    return dict(document_catalog=catalog(root,files),units=units,interfaces=interfaces,types=types,documents=candidates,gaps=gaps,interface_count=sum(len(x['functions']) for x in interfaces if not x['auxiliary']),indexed_function_count=sum(len(x['functions']) for x in interfaces))


def relevant(interfaces,documents,limit=60,*,public_only=True):
    text='\n'.join(d['content'] for d in documents)
    tokens=set(re.findall(r'[A-Za-z_][A-Za-z_0-9]{2,}',text))
    def score(row):
        names={f['name'] for f in row['functions']}
        return (-len(names&tokens),row['auxiliary'],*rank(row['path']))
    eligible=[row for row in interfaces if not public_only or not row['auxiliary']]
    selected=sorted(eligible,key=score)[:limit]
    return selected,dict(total=len(interfaces),included=len(selected),omitted=max(0,len(interfaces)-len(selected)),auxiliary_omitted=len(interfaces)-len(eligible),method='public component interfaces ranked by document symbols; native tests and full index archived separately')


def batches(root,documents,max_chars=18000):
    current=[];size=0
    for doc in documents:
        text=(root/doc['path']).read_text(errors='strict');offset=0
        while offset<len(text):
            end=min(len(text),offset+10000)
            if end<len(text):
                newline=text.rfind('\n',offset,end)
                if newline>offset+500:end=newline+1
            part=dict(id='D'+sha((doc['path']+':'+str(offset)).encode())[:12],title=doc['path'],origin=f"{doc['path']}#chars={offset}:{end}",content=text[offset:end])
            if current and (size+len(part['content'])>max_chars or len(current)>=4):yield current;current=[];size=0
            current.append(part);size+=len(part['content']);offset=end
    if current:yield current
