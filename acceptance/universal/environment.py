"""Declared optional setup in the disposable workspace, with per-action receipts."""
import json
import re
from packaging.specifiers import SpecifierSet
from packaging.version import Version
from ..integrations.formats import require
from ..integrations.runner import encode


def python_images(unit,images):
    constraint=unit.get('settings',{}).get('project',{}).get('requires-python','')
    allowed=SpecifierSet(constraint)
    candidates=[]
    for key,image in images.items():
        if not key.startswith('universal-python'):continue
        probe=image.get('versions',{}).get('python',{})
        match=re.search(r'Python ([0-9]+\.[0-9]+\.[0-9]+)',probe.get('text',''))
        if probe.get('exit_code')==0 and match and Version(match[1]) in allowed:candidates.append((Version(match[1]),key))
    require(candidates,'现有隔离镜像不满足声明的 Python 版本：'+constraint)
    return [key for _,key in sorted(candidates,reverse=True)]


def python_image(unit,images):return python_images(unit,images)[0]


def prepare_candidates(run,unit,output,cancelled,prepare):
    """Probe bootstrap compatibility only; never retry failed business assertions."""
    from .runtime import command,result_file
    choices=run.setdefault('universal_environment_choices',{})
    attempts=run.setdefault('universal_environment_attempts',{}).setdefault(unit['id'],[])
    require(not attempts,'运行环境已经有准备记录，不能覆盖')
    modules=sorted(set(unit.get('provides',[]))|{s['module'] for s in unit.get('services',[]) if s.get('module')})
    modules=[m for m in modules if re.fullmatch(r'[A-Za-z_][A-Za-z_0-9]*(?:\.[A-Za-z_][A-Za-z_0-9]*)*',m)]
    prepared=[];chosen=None
    try:
        for index,key in enumerate(python_images(unit,run['images'])):
            if cancelled():raise ValueError('运行环境准备已取消')
            choices[unit['id']]=index
            out=output/('runtime-'+str(index));out.mkdir()
            attempt=dict(index=index,image_key=key,image=run['images'][key]['id'],status='preparing',probes=[])
            attempts.append(attempt)
            # Installation/network/isolation failures retain their own status;
            # only an installed environment with failed import probes tries an
            # alternative declared-compatible runtime.
            report,cmd=prepare(run,unit,out,cancelled,image_key=key)
            prepared.append((report,cmd))
            for number,module in enumerate(modules):
                if cancelled():raise ValueError('运行环境准备已取消')
                dest=out/('public-import-'+str(number));dest.mkdir()
                probe,_=command(run,unit,['/work/venv/bin/python','-P','-c','import importlib,sys; importlib.import_module(sys.argv[1])',module],dest,cancelled,timeout=run.get('_task_timeout',900),offline=True)
                attempt['probes'].append(dict(module=module,command=probe,status='passed' if probe['exit_code']==0 else 'error',evidence=str(dest.relative_to(output))))
            attempt['status']='ready' if all(p['status']=='passed' for p in attempt['probes']) else 'import-error'
            if attempt['status']=='ready':chosen=index;break
        # If no candidate imports all declared entries, retain the preferred
        # runtime and expose partial readiness; independent checks still run.
        if chosen is None:chosen=0
        choices[unit['id']]=chosen
        selected,cmd=prepared[chosen]
        rows=[dict(name=x['name'],status=x['status'],detail=x.get('detail') or '') for x in selected['tests']]
        for probe in attempts[chosen]['probes']:
            if probe['status']=='error':rows.append(dict(name='可选准备 · 公开入口 '+probe['module'],status='error',detail='所有候选环境均未全部就绪；实际导入错误见 '+probe['evidence']))
        return result_file(output,rows),cmd
    except BaseException:
        if attempts and attempts[-1]['status']=='preparing':attempts[-1]['status']='preparation-error'
        raise
    finally:
        receipt=dict(version=1,unit=unit['id'],constraint=unit.get('settings',{}).get('project',{}).get('requires-python',''),modules=modules,selected=chosen,attempts=attempts,scope='declared runtime bootstrap compatibility; not business validation')
        (output/'environment-selection.json').write_bytes(encode(receipt))


def verify_selection(store,run):
    """Bind mutable execution routing to the archived environment decisions."""
    choices=run.get('universal_environment_choices',{})
    attempts=run.get('universal_environment_attempts',{})
    units={u['id']:u for u in run['universal_plan']['discovery']['units'] if u['runtime']=='python'}
    require(set(choices)<=set(units) and set(attempts)<=set(units),'运行环境包含未声明组件')
    for task in run['tasks']:
        if task['tool']!='universal-prepare' or task['target'] not in units or task['state'] not in {'completed','error','cancelled'}:continue
        uid=task['target'];unit=units[uid]
        artifact=next((a for a in run['artifacts'] if a['name']==task['id']+'/environment-selection.json'),None)
        # Failures before runtime preparation have no selection to archive.
        if uid not in attempts:
            require(task['state']!='completed' and uid not in choices and artifact is None,'运行环境选择原件缺失');continue
        require(artifact is not None,'运行环境选择原件缺失')
        receipt=json.loads(store.artifact_bytes_for_record(run,artifact['id'])[1])
        expected_modules=sorted(set(unit.get('provides',[]))|{s['module'] for s in unit.get('services',[]) if s.get('module')})
        expected_modules=[m for m in expected_modules if re.fullmatch(r'[A-Za-z_][A-Za-z_0-9]*(?:\.[A-Za-z_][A-Za-z_0-9]*)*',m)]
        require(receipt['unit']==uid and receipt['constraint']==unit.get('settings',{}).get('project',{}).get('requires-python','') and receipt['modules']==expected_modules,'运行环境选择范围不一致')
        rows=receipt['attempts'];require(rows and rows==attempts[uid],'运行环境尝试与原件不一致')
        candidates=python_images(unit,run['images'])
        for i,row in enumerate(rows):
            require(i<len(candidates) and type(row['index']) is int and row['index']==i and row['image_key']==candidates[i] and row['image']==run['images'][candidates[i]]['id'],'运行环境镜像或顺序不属于冻结候选')
        selected=receipt['selected'];effective=len(rows)-1 if selected is None else selected
        require(type(effective) is int and 0<=effective<len(rows) and type(choices.get(uid)) is int and choices.get(uid)==effective,'运行环境选择与原件不一致')
        require(task['state']!='completed' or selected is not None,'准备完成却没有选定运行环境')


def execute(run,unit,output,cancelled):
    from .runtime import command,docker,names
    plan=unit.get('environment_preparation',{});rows=[]
    def call(label,args,offline=False):
        out=output/label;out.mkdir()
        cmd,_=command(run,unit,args,out,cancelled,timeout=run.get('_task_timeout',900),offline=offline)
        return cmd
    for i,item in enumerate(plan.get('optional_packages',[])):
        row=dict(kind='optional-package',spec=item['spec'],origins=item['origins']);rows.append(row)
        module=item['spec'] if all(o.get('kind')=='optional-import' for o in item['origins']) else None
        row['identity']='optional module candidate; verified by import' if module else 'explicit CI distribution'
        probe=['/work/venv/bin/python','-c','import importlib,sys; importlib.import_module(sys.argv[1])',module] if module else ['/work/venv/bin/python','-c','import importlib.metadata,sys; name,_,expected=sys.argv[1].partition("=="); actual=importlib.metadata.version(name); print(actual); sys.exit(0 if not expected or actual==expected else 1)',item['spec']]
        try:
            initial=call('optional-'+str(i)+'-probe',probe);row['probe']=initial
            if initial['exit_code']==0:
                row['status']='already-present';continue
            dest='/work/optional-'+str(i)+'-install.json'
            install=call('optional-'+str(i)+'-install',['/work/venv/bin/python','-m','pip','install','--report',dest,item['spec']]);row['install']=install
            docker('cp',names(run,unit)[0]+':'+dest,str(output/('optional-'+str(i)+'-install')/'pip-report.json'),check=False)
            if install['exit_code']!=0:
                row.update(status='error',reason='可选依赖安装失败');continue
            verified=call('optional-'+str(i)+'-verify',probe);row['verification']=verified
            row.update(status='prepared' if verified['exit_code']==0 else 'error',reason='' if verified['exit_code']==0 else '安装后仍无法导入声明模块')
        except (ValueError,OSError) as exc:row.update(status='error',reason=str(exc))
    for i,item in enumerate(plan.get('build_actions',[])):
        row=dict(kind='declared-build',action=item);rows.append(row)
        try:
            # shell text is fixed; every target-derived token is a separate argv.
            cmd=call('declared-build-'+str(i),['/bin/sh','-c','cd "$1" && shift && exec "$@"','acceptance','/work/repo/'+item['workdir'],*item['argv']],offline=True)
            row.update(command=cmd,status='prepared' if cmd['exit_code']==0 else 'error',reason='' if cmd['exit_code']==0 else '声明的测试扩展构建失败')
        except (ValueError,OSError) as exc:row.update(status='error',reason=str(exc))
    report=dict(version=1,actions=rows,system_declarations=plan.get('system_declarations',[]),scope=plan.get('scope'))
    (output/'optional-preparation.json').write_bytes(encode(report))
    return report
