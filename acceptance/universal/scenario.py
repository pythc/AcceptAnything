"""Target-side stateful invocation; input contains no expected values or assertions."""
import asyncio
import base64
import dataclasses
import importlib
import importlib.util
import inspect
import json
import os
import sys
import tempfile
import subprocess
from pathlib import Path

if __package__:
    from .python_imports import load
else:
    sys.path.insert(0,str(Path(__file__).resolve().parent))
    from python_imports import load


class ProtocolError(ValueError):pass


def member(name):
    if not isinstance(name,str) or not name.isidentifier() or name.startswith('_') or name in {'constructor','prototype'}:
        raise ValueError('private member unavailable')
    return name


def observable(value):
    def default(v):
        if dataclasses.is_dataclass(v) and not isinstance(v,type):return dataclasses.asdict(v)
        if callable(getattr(v,'model_dump',None)):return v.model_dump(mode='json')
        raise TypeError('opaque value')
    try:return True,json.loads(json.dumps(value,default=default,allow_nan=False))
    except (ValueError,TypeError,OverflowError,RecursionError):return False,{'handle_type':type(value).__name__}


def process_result(value):
    """Observe mature process-result objects without inventing a verdict."""
    if isinstance(value,subprocess.CompletedProcess):
        result=dict(adapter='python.subprocess.CompletedProcess',exit_code=value.returncode)
        fields={'stdout':value.stdout,'stderr':value.stderr}
    elif any(cls.__module__=='click.testing' and cls.__name__=='Result' for cls in type(value).__mro__):
        from click.testing import Result
        if not isinstance(value,Result):return None
        result=dict(adapter='click.testing.Result',exit_code=value.exit_code)
        exc=value.exception
        result['exception']=dict(type=type(exc).__name__,module=type(exc).__module__,message=str(exc)) if exc is not None else None
        fields={}
        for name in ('stdout','stderr','output','stdout_bytes','stderr_bytes','output_bytes'):
            try:fields[name]=getattr(value,name)
            except (AttributeError,ValueError) as exc:result.setdefault('unavailable_fields',{})[name]=str(exc)
    else:return None
    for name,raw in fields.items():
        if isinstance(raw,bytes):result[name]=dict(encoding='base64',value=base64.b64encode(raw).decode('ascii'))
        elif raw is None or isinstance(raw,str):result[name]=raw
        else:result.setdefault('unavailable_fields',{})[name]='unsupported stream type'
    return result


def project(value,pointer):
    if not pointer.startswith('/'):raise ValueError('observation requires a field path')
    for part in pointer[1:].split('/'):
        key=part.replace('~1','/').replace('~0','~')
        if isinstance(value,dict) or callable(getattr(value,'keys',None)) and callable(getattr(value,'__getitem__',None)):value=value[key]
        elif isinstance(value,(list,tuple)):
            if not key.isdecimal():raise ValueError('invalid array index')
            value=value[int(key)]
        else:value=getattr(value,member(key))
    return value


async def execute(request,root,on_ready=None):
    root=Path(root).resolve()
    state={};contexts={};rows=[];clean=[];callbacks=[];callback_errors=[];callback_count=0;failed=False
    with tempfile.TemporaryDirectory(prefix='acceptance-case-') as temporary:
        work=Path(temporary).resolve();previous=Path.cwd();os.chdir(work)
        def path(name):
            result=(work/name).resolve()
            if not result.is_relative_to(work):raise ValueError('fixture outside case directory')
            return result
        def resolve(value,scope=None):
            nonlocal callback_count
            scope=state if scope is None else scope
            if isinstance(value,list):return [resolve(v,scope) for v in value]
            if not isinstance(value,dict):return value
            if '$ref' in value:
                result=scope[value['$ref']]
                return project(result,value['pointer']) if 'pointer' in value else result
            if '$path' in value:return str(path(value['$path']))
            if '$callback' in value:
                cb=value['$callback'];captured=dict(scope)
                callback_count+=1;name='acceptance_callback_'+str(callback_count)
                def begin(args,kwargs):
                    local={**captured,**dict(zip(cb.get('params',[]),args)),**kwargs}
                    log=dict(id=name,status='running',calls=[]);callbacks.append(log);return local,log
                def invoke(call,local):
                    return getattr(local[call['target']],member(call['member']))(*resolve(call.get('args',[]),local),**resolve(call.get('kwargs',{}),local))
                def save(call,result,local,log):
                    local[call['id']]=result;ok,shown=observable(result)
                    log['calls'].append(dict(id=call['id'],member=call['member'],status='completed',observable=ok,value=shown))
                def callback(*args,**kwargs):
                    local,log=begin(args,kwargs)
                    try:
                        for call in cb.get('calls',[]):save(call,invoke(call,local),local,log)
                        result=resolve(cb['return'],local);visible,shown=observable(result);log.update(status='completed',return_value=dict(observable=visible,value=shown));return result
                    except (Exception,SystemExit) as exc:
                        log.update(status='error',error=type(exc).__name__+': '+str(exc));callback_errors.append((log,exc));raise
                callback.__name__=name
                if cb.get('async'):
                    async def asynchronous(*args,**kwargs):
                        local,log=begin(args,kwargs)
                        try:
                            for call in cb.get('calls',[]):
                                result=invoke(call,local)
                                if inspect.isawaitable(result):result=await result
                                save(call,result,local,log)
                            result=resolve(cb['return'],local);visible,shown=observable(result);log.update(status='completed',return_value=dict(observable=visible,value=shown));return result
                        except (Exception,SystemExit) as exc:
                            log.update(status='error',error=type(exc).__name__+': '+str(exc));callback_errors.append((log,exc));raise
                    asynchronous.__name__=name
                    return asynchronous
                return callback
            return {k:resolve(v,scope) for k,v in value.items()}
        async def step(s,is_cleanup=False):
            op=s['op'];target=state.get(s.get('target'));value=None
            if s.get('target') and s['target'] not in state:raise ValueError('prerequisite object unavailable')
            if op in {'call','observe_call'}:
                fn=getattr(load(root,s['module']),member(s['export'])) if s.get('module') else getattr(target,member(s['member'])) if s.get('member') else target
                if not callable(fn):raise ValueError('public callable unavailable')
                args=resolve(s.get('args',[]));kwargs=resolve(s.get('kwargs',{}))
                callback_start=len(callback_errors)
                try:
                    value=fn(*args,**kwargs)
                    if inspect.isawaitable(value):value=await value
                except Exception as exc:
                    if op!='observe_call':raise
                    if request.get('observe_callback_errors') and not is_cleanup:
                        for log,error in callback_errors[callback_start:]:
                            if error is exc:log.update(status='observed-error',observed_by=s['id'])
                    value=dict(raised=True,exception=dict(type=type(exc).__name__,module=type(exc).__module__,message=str(exc)))
                else:
                    if op=='observe_call':
                        visible,shown=observable(value)
                        value=dict(raised=False,return_observable=visible,**({'value':shown} if visible else {}))
            elif op=='get':value=getattr(target,member(s['member']))
            elif op=='item':value=target[resolve(s['value'])]
            elif op=='collect':value=list(target)
            elif op=='identity':
                other=resolve(s['value'])
                primitives=(str,bytes,int,float,bool,tuple,frozenset,type(None))
                if isinstance(target,primitives) or isinstance(other,primitives):raise ValueError('identity requires object handles, not scalar values')
                value=target is other
            elif op=='inspect_path':
                if not isinstance(target,(str,os.PathLike)):raise ValueError('path observation requires a path value')
                dest=Path(target).resolve()
                if not (dest.is_relative_to(work) or dest.is_relative_to(root)):raise ValueError('path observation outside isolated source and case directories')
                value=dict(path=str(dest),exists=dest.exists(),is_file=dest.is_file(),is_dir=dest.is_dir())
            elif op=='enter':
                if hasattr(target,'__aenter__'):value=await target.__aenter__();contexts[s['id']]=(target,True)
                elif hasattr(target,'__enter__'):value=target.__enter__();contexts[s['id']]=(target,False)
                else:raise ProtocolError('enter target is not a context manager; call the public context factory first')
            elif op=='exit':
                key=s['target']
                if key not in contexts:
                    # A context manager and its __enter__ result may differ.
                    # Resolve only a unique active manager, never exit twice.
                    candidates=[k for k,(manager,_) in contexts.items() if manager is state.get(key)]
                    if len(candidates)!=1:raise ValueError('exit target must identify one active context')
                    key=candidates[0]
                context,asynchronous=contexts.pop(key)
                value=await context.__aexit__(None,None,None) if asynchronous else context.__exit__(None,None,None)
            elif op=='write_file':
                dest=path(s['path']);dest.parent.mkdir(parents=True,exist_ok=True)
                encoding=s.get('encoding','utf-8')
                if encoding not in {'utf-8','latin-1','ascii','base64'}:raise ProtocolError('unsupported fixture encoding')
                raw=base64.b64decode(s['value'],validate=True) if encoding=='base64' else s['value'].encode(encoding)
                dest.write_bytes(raw);value=str(dest)
            elif op=='cli':
                import site,hashlib
                def pth_files():
                    return {p:hashlib.sha256(p.read_bytes()).hexdigest() for directory in site.getsitepackages() for p in Path(directory).glob('*.pth') if p.is_file()}
                before=pth_files() if request.get('refresh_installed_packages') else {};refreshed=[]
                args=resolve(s.get('argv',[]))
                if not all(isinstance(a,str) and '\0' not in a for a in args):raise ValueError('CLI arguments must be strings')
                result=subprocess.run([*s['command'],*args],input=s.get('stdin',''),capture_output=True,text=True,timeout=90)
                value=dict(exit_code=result.returncode,stdout=result.stdout,stderr=result.stderr)
                # New editable installs add .pth finders after this interpreter
                # started. Process only new/changed files as Python startup
                # would; never reload target modules or change its objects.
                if result.returncode==0 and request.get('refresh_installed_packages'):
                    for file,digest in pth_files().items():
                        if before.get(file)==digest:continue
                        site.addpackage(str(file.parent),file.name,None);refreshed.append(dict(file=str(file),sha256=digest,adapter='stdlib site.addpackage'))
                    importlib.invalidate_caches()
            else:raise ValueError('unknown operation')
            state[s['id']]=value;ok,shown=observable(value)
            row=dict(id=s['id'],status='completed',observable=ok,value=shown)
            if op=='cli' and result.returncode==0 and refreshed:row['import_refresh']=refreshed
            if request.get('observe_process_results') and op=='call':
                try:
                    invocation=process_result(value)
                    if invocation is not None:row['process_result']=invocation
                except Exception as exc:row['process_result_observation_error']=type(exc).__name__+': '+str(exc)
            if not ok:
                observations=[]
                for observation in request.get('observations',[]):
                    if observation['step']!=s['id']:continue
                    try:
                        visible,field=observable(project(value,observation['pointer']))
                        observations.append(dict(pointer=observation['pointer'],observable=visible,value=field))
                    except (Exception,SystemExit) as exc:
                        observations.append(dict(pointer=observation['pointer'],observable=False,error=type(exc).__name__+': '+str(exc)))
                if observations:row['observations']=observations
            return row
        try:
            for s in request['steps']:
                if failed:rows.append(dict(id=s['id'],status='blocked',reason='prior step failed'));continue
                try:rows.append(await step(s))
                except (Exception,SystemExit) as exc:
                    failed=True;rows.append(dict(id=s['id'],status='error',error=type(exc).__name__+': '+str(exc),**({'error_origin':'protocol'} if isinstance(exc,ProtocolError) else {})))
            if on_ready is not None and not failed:
                try:await on_ready(state,work,rows)
                except (Exception,SystemExit) as exc:
                    failed=True;rows.append(dict(id='managed-session',status='error',error=type(exc).__name__+': '+str(exc)))
            for s in request.get('cleanup',[]):
                try:clean.append(await step(s,is_cleanup=True))
                except (Exception,SystemExit) as exc:
                    failed=True;clean.append(dict(id=s['id'],status='error',error=type(exc).__name__+': '+str(exc)))
        finally:
            for key,(context,asynchronous) in reversed(list(contexts.items())):
                try:
                    if asynchronous:await context.__aexit__(None,None,None)
                    else:context.__exit__(None,None,None)
                    clean.append(dict(id=key,status='completed',automatic_context_exit=True))
                except Exception as exc:
                    failed=True;clean.append(dict(id=key,status='error',error=type(exc).__name__+': '+str(exc)))
            os.chdir(previous)
    return dict(status='error' if failed or any(c['status'] not in {'completed','observed-error'} for c in callbacks) else 'completed',steps=rows,cleanup=clean,callbacks=callbacks,temporary_directory_removed=not work.exists())


if __name__=='__main__':
    request=json.loads(base64.b64decode(sys.argv[1]))
    print('\nACCEPTANCE_VALUE:'+json.dumps(asyncio.run(execute(request,Path('/work/repo'))),ensure_ascii=False,allow_nan=False))
