"""Conservative, data-only discovery of optional test environment declarations."""
import ast
import re
import shlex
import sys
from pathlib import PurePosixPath
import yaml


def linux_condition(value,matrix_os='ubuntu-latest'):
    if value is None:return True
    value=str(value).strip().removeprefix('${{').removesuffix('}}').strip()
    # Only proven OS clauses; secrets, custom expressions and version-specific
    # jobs are not interpreted or executed as a general-purpose CI runner.
    match=re.fullmatch(r"(matrix\.os|runner\.os)\s*(==|!=)\s*['\"]([^'\"]+)['\"]",value)
    if not match:return False
    name,op,target=match.groups();current=matrix_os if name=='matrix.os' else 'Linux'
    return (current==target)==(op=='==')


def compile_action(command,workdir,files):
    # No shell evaluation. Accept a conventional cd && compiler invocation;
    # trailing ls is informational only and is not executed.
    text=command.strip().strip('()').strip()
    try:tokens=shlex.split(text)
    except ValueError:return None
    if tokens[:1]==['cd']:
        if len(tokens)<4 or tokens[2]!='&&':return None
        workdir=str(PurePosixPath(workdir)/tokens[1]);tokens=tokens[3:]
    if '&&' in tokens:
        index=tokens.index('&&')
        if tokens[index+1:index+2]!=['ls']:return None
        tokens=tokens[:index]
    if not tokens or tokens[0] not in {'cc','gcc','clang','g++','c++','clang++'}:return None
    path=PurePosixPath(workdir)
    if path.is_absolute() or '..' in path.parts or '$' in workdir:return None
    args=tokens[1:];sources=[];output=None;index=0
    while index<len(args):
        value=args[index]
        if value=='-o':
            index+=1
            if index==len(args) or output is not None:return None
            output=str(path/args[index]);p=PurePosixPath(output)
            if p.is_absolute() or '..' in p.parts or output in files or not re.fullmatch(r'[\w./-]+',output):return None
        elif value in {'-shared','-fPIC','-fpic','-g','-Wall','-Wextra','-O0','-O1','-O2','-O3'}:pass
        elif re.fullmatch(r'-std=(?:c|gnu|c\+\+|gnu\+\+)\d+',value):pass
        elif PurePosixPath(value).suffix in {'.c','.cc','.cpp'}:
            source=str(path/value)
            if source not in files or PurePosixPath(value).is_absolute() or '..' in PurePosixPath(value).parts:return None
            sources.append(source)
        else:return None
        index+=1
    return dict(kind='compile',argv=tokens,workdir=str(path),inputs=sources,output=output) if output and sources else None


def discover(root,files,unit):
    actions=[];declarations=[];optional={};prefix=unit['path']
    for file in files:
        if not file.startswith('.github/workflows/') or PurePosixPath(file).suffix not in {'.yml','.yaml'}:continue
        try:data=yaml.safe_load((root/file).read_text()) or {}
        except (yaml.YAMLError,UnicodeError):continue
        if not isinstance(data,dict) or not isinstance(data.get('jobs'),dict):continue
        for name,job in data['jobs'].items():
            if not isinstance(job,dict):continue
            runner=job.get('runs-on')
            linux_runners=[runner] if isinstance(runner,str) and runner.startswith('ubuntu-') else ['ubuntu-latest']
            if isinstance(runner,str) and '${{' not in runner and not runner.startswith('ubuntu-'):continue
            if isinstance(runner,list):continue  # unverified self-hosted labels
            if isinstance(runner,str) and '${{' in runner:
                if runner.strip()!='${{ matrix.os }}':continue
                strategy=job.get('strategy',{});matrix=strategy.get('matrix',{}) if isinstance(strategy,dict) else {}
                operating_systems=matrix.get('os',[]) if isinstance(matrix,dict) else []
                if not isinstance(operating_systems,list) or not any(isinstance(os,str) and os.startswith('ubuntu-') for os in operating_systems):continue
                linux_runners=[os for os in operating_systems if isinstance(os,str) and os.startswith('ubuntu-')]
            linux_runners=[os for os in linux_runners if linux_condition(job.get('if'),os)]
            if not linux_runners:continue
            defaults=job.get('defaults',{})
            defaults=defaults.get('run',{}) if isinstance(defaults,dict) else {}
            default_dir=defaults.get('working-directory','.') if isinstance(defaults,dict) else '.'
            steps=job.get('steps',[])
            if not isinstance(steps,list) or not any(isinstance(s,dict) and re.search(r'\bpytest\b',str(s.get('run',''))) for s in steps):continue
            first_test=next(i for i,s in enumerate(steps) if isinstance(s,dict) and re.search(r'\bpytest\b',str(s.get('run',''))))
            for index,step in enumerate(steps[:first_test]):
                if not isinstance(step,dict) or not isinstance(step.get('run'),str) or not all(linux_condition(step.get('if'),os) for os in linux_runners):continue
                workdir=step.get('working-directory',default_dir)
                if workdir!=prefix:continue
                origin=dict(file=file,job=str(name),step=index,condition=step.get('if'),linux_variants=linux_runners)
                for line in step['run'].splitlines():
                    compiled=compile_action(line,workdir,set(files))
                    if compiled:actions.append(dict(**compiled,origin=origin));continue
                    try:argv=shlex.split(line)
                    except ValueError:continue
                    if argv[:3]==['python','-m','pip']:argv=argv[2:]
                    if argv[:2]==['pip','install'] and argv[2:] and all(re.fullmatch(r'[A-Za-z][A-Za-z0-9_-]*(?:==[0-9][A-Za-z0-9_.-]*)?',p) for p in argv[2:]):
                        for package in argv[2:]:optional.setdefault(package,[]).append(dict(**origin,kind='declared-package'))
                    if re.search(r'\bapt-get install\b',line):declarations.append(dict(kind='system-packages',command=line,origin=origin,status='requires-image-capability'))
    local=set(unit.get('provides',[]))|{PurePosixPath(n).stem for n in files if PurePosixPath(n).parent==PurePosixPath(prefix)}
    local|={PurePosixPath(n).stem for n in unit.get('test_files',[]) if n.endswith('.py')}
    for file in unit.get('test_files',[]):
        if not file.endswith('.py'):continue
        try:tree=ast.parse((root/file).read_text())
        except (SyntaxError,UnicodeError):continue
        for node in ast.walk(tree):
            if not isinstance(node,ast.Try):continue
            handlers={n.id for h in node.handlers for n in ast.walk(h.type) if isinstance(n,ast.Name)} if all(h.type is not None for h in node.handlers) else set()
            if not handlers&{'ImportError','ModuleNotFoundError'}:continue
            for branch in node.body:
                for imp in ast.walk(branch):
                    names=[n.name.split('.')[0] for n in imp.names] if isinstance(imp,ast.Import) else [imp.module.split('.')[0]] if isinstance(imp,ast.ImportFrom) and not imp.level and imp.module else []
                    for name in names:
                        if name not in local and name not in sys.stdlib_module_names and re.fullmatch(r'[A-Za-z][A-Za-z0-9_]*',name):optional.setdefault(name,[]).append(dict(file=file,line=imp.lineno,kind='optional-import',distribution_identity='same-name-candidate; verify module after install'))
    dedup={}
    for action in actions:
        key=(action['workdir'],tuple(action['argv']))
        if key not in dedup:dedup[key]=action
    return dict(version=1,optional_packages=[dict(spec=p,origins=origins) for p,origins in sorted(optional.items())],build_actions=list(dedup.values()),system_declarations=declarations,scope='declared local preparation; not a complete CI matrix or arbitrary workflow execution')
