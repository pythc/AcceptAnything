"""Static HTTP locators from Python AST. Paths are plumbing, never oracles."""
import ast
from pathlib import Path
from hashlib import sha256


def literal(node):
    try:return ast.literal_eval(node)
    except (ValueError,TypeError,SyntaxError):return None


def discover(root,files,units,owner):
    for u in units:
        if u['runtime']!='python':continue
        records=[];objects={};registrations=[];imports={};module_files={}
        def module_name(name):
            rel=Path(name).relative_to(u['path']).with_suffix('');parts=list(rel.parts)
            if parts and parts[0]=='src':parts.pop(0)
            if parts and parts[-1]=='__init__':parts.pop()
            return '.'.join(parts)
        eligible=[n for n in files if n.endswith('.py') and owner(n,'python')==u]
        module_files={module_name(n):n for n in eligible}
        for name in files:
            if not name.endswith('.py') or owner(name,'python')!=u:continue
            if set(Path(name).relative_to(u['path']).parts)&{'tests','test','fixtures','testdata','benchmarks'}:continue
            try:tree=ast.parse((root/name).read_text())
            except (SyntaxError,UnicodeError):continue
            digest=sha256((root/name).read_bytes()).hexdigest()
            namespace=module_name(name);package=namespace if Path(name).name=='__init__.py' else namespace.rpartition('.')[0]
            imported={}
            for n in ast.walk(tree):
                if isinstance(n,ast.ImportFrom):
                    base=package.split('.')[:len(package.split('.'))-n.level+1] if n.level else []
                    prefix='.'.join([*base,*([n.module] if n.module else [])])
                    for a in n.names:
                        imported[a.asname or a.name]=(prefix+'.'+a.name).strip('.')
                elif isinstance(n,ast.Import):
                    for a in n.names:imported[a.asname or a.name.split('.')[0]]=a.name if a.asname else a.name.split('.')[0]
            imports[name]=imported
            aliases={a.asname or a.name:a.name for n in ast.walk(tree) if isinstance(n,ast.ImportFrom) and n.module in {'flask','fastapi'} for a in n.names if a.name in {'Blueprint','Flask','FastAPI','APIRouter'}}
            local={}
            for n in ast.walk(tree):
                if isinstance(n,(ast.Assign,ast.AnnAssign)):
                    targets=n.targets if isinstance(n,ast.Assign) else [n.target]
                    if not isinstance(n.value,ast.Call) or not isinstance(n.value.func,ast.Name) or n.value.func.id not in aliases:continue
                    for target in targets:
                        if not isinstance(target,ast.Name):continue
                        call=n.value;kind=aliases[call.func.id];kw={x.arg:literal(x.value) for x in call.keywords};prefix=kw.get('url_prefix',kw.get('prefix',''))
                        local[target.id]=dict(kind=kind,prefix=prefix,name=literal(call.args[0]) if call.args else None)
            objects[name]=local
            for n in ast.walk(tree):
                if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr in {'register_blueprint','include_router'} and n.args:
                    kw={x.arg:literal(x.value) for x in n.keywords}
                    if 'url_prefix' in kw or 'prefix' in kw:
                        registrations.append(dict(file=name,expression=ast.unparse(n.args[0]),prefix=kw.get('url_prefix',kw.get('prefix')),operation=n.func.attr))
                if not isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)):continue
                for d in n.decorator_list:
                    if not isinstance(d,ast.Call) or not isinstance(d.func,ast.Attribute) or not isinstance(d.func.value,ast.Name):continue
                    if d.func.attr not in {'route','get','post','put','patch','delete','head','options'} or not d.args:continue
                    path=literal(d.args[0]);obj=local.get(d.func.value.id)
                    if not obj or not isinstance(path,str) or not path.startswith('/'):continue
                    prefix=obj['prefix'];kw={k.arg:literal(k.value) for k in d.keywords}
                    endpoint=kw.get('endpoint') or n.name
                    if obj['kind']=='Blueprint' and isinstance(obj['name'],str):endpoint=obj['name']+'.'+endpoint
                    methods=kw.get('methods') if d.func.attr=='route' else [d.func.attr.upper()]
                    if methods is None:methods=['GET']
                    bound=prefix.rstrip('/')+path if isinstance(prefix,str) else None
                    records.append(dict(path=bound,local_path=path,endpoint=endpoint,methods=methods,receiver=d.func.value.id,source=dict(path=name,line=d.lineno,sha256=digest),binding='literal-decorator',notes=[]))
        for reg in registrations:
            expr=reg['expression'];head,_,tail=expr.partition('.');alias=imports.get(reg['file'],{}).get(head)
            if alias:
                identity=alias+('.'+tail if tail else '');module,_,variable=identity.rpartition('.')
                reg['target_file']=module_files.get(module);reg['target_variable']=variable
            else:reg.update(target_file=reg['file'],target_variable=expr)
        bound=[]
        for row in records:
            matches=[r for r in registrations if r.get('target_file')==row['source']['path'] and r.get('target_variable')==row['receiver']]
            if not matches:bound.append(row);continue
            for reg in matches:
                item={**row,'notes':[dict(kind='registration-prefix',**reg)]}
                if isinstance(reg['prefix'],str):
                    suffix=row['path'] if reg['operation']=='include_router' else row['local_path']
                    item['path']=reg['prefix'].rstrip('/')+suffix if suffix else None;item['binding']='literal-registration'
                else:item.update(path=None,binding='registration-needs-binding')
                bound.append(item)
        u['route_bindings']=bound
