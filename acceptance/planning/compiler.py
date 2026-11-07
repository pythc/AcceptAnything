"""Expand an independent specification into reviewed, executable test artifacts."""
from itertools import product
import json
from pathlib import Path
import re
from time import perf_counter
import uuid
import importlib.metadata
from .models import DesignInput, DIMENSIONS, Assertion, Step
from pydantic import TypeAdapter
from ..integrations.discovery import inventory, manifest
from ..integrations.runner import sha, encode
from ..integrations.registry import ROOT, locks
from ..integrations.formats import require

RUNTIME = Path(__file__).parent / 'runtime'
TOKEN = re.compile(r'\$\{([A-Za-z][A-Za-z0-9_-]*)\}')


def substitute(value, values):
    if isinstance(value, list): return [substitute(x, values) for x in value]
    if isinstance(value, dict): return {k: substitute(v, values) for k, v in value.items()}
    if not isinstance(value, str): return value
    match = TOKEN.fullmatch(value)
    if match and match[1] in values: return values[match[1]]
    def replace(m):
        if m[1] not in values: return m[0]
        item = values[m[1]]
        require(isinstance(item, (str, int, float, bool)), '文本插值只能引用标量')
        return str(item)
    return TOKEN.sub(replace, value)


def variants(scenario):
    if scenario.examples: return scenario.examples
    if scenario.matrix:
        size = 1
        for v in scenario.matrix.values(): size *= len(v)
        require(size <= 200, '场景矩阵超过200项，请缩小范围')
        return [dict(zip(scenario.matrix, values)) for values in product(*scenario.matrix.values())]
    if scenario.boundary:
        b = scenario.boundary
        points = [(b.minimum-b.step, b.invalid), (b.minimum,b.valid),
                  ((b.minimum+b.maximum)/2,b.valid), (b.maximum,b.valid), (b.maximum+b.step,b.invalid)]
        require(b.variable != 'expected', '边界变量不能占用 expected')
        return [{b.variable: int(x) if x.is_integer() else x, 'expected': result} for x,result in points]
    return [{}]


def dependencies():
    from ..engine import NODE
    versions = {name: importlib.metadata.version(name) for name in ('pytest','jsonschema','pydantic')}
    package = ROOT / 'validation/node_modules/@playwright/test/package.json'
    versions['playwright'] = json.loads(package.read_text())['version'] if package.exists() else None
    versions['node_binary'] = str(NODE)
    versions['node_sha256'] = sha(Path(NODE).read_bytes())
    versions['images'] = {k: locks().get(k,{}).get('id') for k in ('node-base','python','gmah-api','gmah-web','gmah-redis','gmah-postgres','gmah-k6')}
    return versions


def compiler_digest():
    paths=[p for p in Path(__file__).parent.rglob('*') if p.suffix in {'.py','.cjs','.mjs'} and '__pycache__' not in p.parts]
    paths += [p for p in (ROOT/'acceptance/recipes/gmah').glob('*') if p.is_file() and p.suffix in {'.py','.js'}]
    paths += list((ROOT/'acceptance/integrations').glob('*.py'))+[ROOT/'acceptance/integrations/gates.rego']
    return sha(encode({str(p.relative_to(ROOT)):sha(p.read_bytes()) for p in sorted(paths)}))


def validate_schema(schema):
    from jsonschema import Draft202012Validator
    if isinstance(schema, dict):
        for k,v in schema.items():
            if k in {'$ref','$dynamicRef'}:
                require(isinstance(v,str) and v.startswith('#'), '契约不允许外部引用')
            validate_schema(v)
    elif isinstance(schema,list):
        for v in schema: validate_schema(v)
    # A full JSON schema is checked at its assertion boundary, not at every property.


def contract_operations(contract):
    require(isinstance(contract,dict) and str(contract.get('openapi','')).startswith('3.'), '需要 OpenAPI 3 JSON 契约')
    paths=contract.get('paths')
    require(isinstance(paths,dict) and paths, 'OpenAPI 契约缺少接口')
    operations=[]
    for path,item in paths.items():
        require(isinstance(path,str) and path.startswith('/') and isinstance(item,dict), '无效 OpenAPI 路径')
        require('$ref' not in item, '请展开 OpenAPI Path Item 引用后生成用例')
        for method in ('get','post','put','patch','delete','head','options','trace'):
            if method not in item: continue
            operation=item[method]
            require(isinstance(operation,dict) and operation.get('responses'), '接口缺少响应契约：'+method+' '+path)
            operations.append(method.upper()+' '+path)
    require(0 < len(operations) <= 200, '契约需要 1–200 个接口操作')
    return operations


def planned_operations(plan, check):
    case=next(c for c in plan['cases'] if c['id']==check['case_ids'][0])
    doc=next(d for d in plan['documents'] if d['id']==case['contract'])
    return contract_operations(json.loads(doc['content']))


def compile_plan(data: DesignInput):
    start=perf_counter()
    root, files, exclusions = inventory(data.repository)
    rows=manifest(str(root),files)
    documents={d.id:d.model_dump() for d in data.documents}
    require(len(documents)==len(data.documents), '验收依据编号重复')
    require(sum(len(d.content.encode()) for d in data.documents)<=512_000, '验收依据合计超过512KB')
    spec=data.specification
    if spec.environment.entrypoint:
        require(spec.environment.entrypoint in files,'服务入口不在冻结文件范围')
        expected_suffixes={'.py'} if spec.environment.runtime=='python' else {'.js','.mjs','.cjs','.ts'}
        require(Path(spec.environment.entrypoint).suffix in expected_suffixes,'入口脚本与运行时不符')
    cases=[]; coverage=[]; omissions=[]; blockers=[]
    for req in spec.requirements:
        require(req.source in documents,'标准引用的文档不存在：'+req.id)
        doc=documents[req.source]; pos=doc['content'].find(req.quote)
        require(pos>=0,'标准引用原文未在依据中找到：'+req.id)
        anchor=dict(source=req.source,title=doc['title'],quote=req.quote,line=doc['content'][:pos].count('\n')+1,sha256=sha(doc['content'].encode()))
        case_ids=[]
        if req.disposition=='excluded': omissions.append(dict(subject=req.title,reason=req.reason))
        if req.disposition=='unresolved': blockers.append(dict(id=req.id,title=req.title,reason=req.reason))
        for scenario in req.scenarios:
            if scenario.engine=='openapi':
                require(scenario.contract in documents,'未找到 OpenAPI 契约')
                contract=json.loads(documents[scenario.contract]['content'])
                contract_operations(contract)
                validate_schema(contract)
            for i,params in enumerate(variants(scenario)):
                require('run_id' not in params, 'run_id 由执行器生成')
                steps=substitute([s.model_dump() for s in scenario.steps],params)
                # Captured values are resolved at runtime; all other placeholders must be defined now.
                available={'run_id'}
                for step in steps:
                    refs=set(TOKEN.findall(json.dumps(step,ensure_ascii=False)))
                    require(refs<=available,'变量未定义：'+','.join(sorted(refs-available)))
                    TypeAdapter(Step).validate_python(step)
                    if step['kind']=='call':
                        require(step['module'] in files,'函数模块不在冻结文件范围')
                        suffix=Path(step['module']).suffix
                        require(suffix in ({'.py'} if spec.environment.runtime=='python' else {'.js','.mjs','.cjs','.ts'}),'函数模块与运行时不符')
                    for a in step.get('assertions',[]):
                        require(a['operator']!='contains' or a['value'] not in ('',[],{}), '包含断言不能为空')
                        if a['operator']=='schema':
                            from jsonschema import Draft202012Validator
                            require(a['value'] not in ({},True),'Schema 断言需要实际约束')
                            validate_schema(a['value']); Draft202012Validator.check_schema(a['value'])
                    captures=step.get('capture',{})
                    require(not set(captures)&available,'捕获变量重复或覆盖保留变量')
                    available.update(captures)
                cid=f'C{len(cases)+1:04d}'
                cases.append(dict(id=cid,name='test_'+cid,title=scenario.title+(f' · {i+1}' if len(variants(scenario))>1 else ''),
                    requirement=req.id,scenario=scenario.id,priority=req.priority,dimension=scenario.dimension,engine=scenario.engine,
                    parameters=params,steps=steps,contract=scenario.contract,source=anchor))
                case_ids.append(cid)
                require(len(cases)<=200,'生成用例超过200项，请缩小验收范围')
        covered={c['dimension'] for c in cases if c['requirement']==req.id}
        coverage.append(dict(id=req.id,title=req.title,priority=req.priority,disposition=req.disposition,reason=req.reason,
                             source=anchor,cases=case_ids,dimensions=[d for d in DIMENSIONS if d in covered]))
    require(cases or blockers,'全部标准都被排除，没有可执行用例')
    toolchain=dependencies()
    require(toolchain['images'][{'node':'node-base','python':'python'}[spec.environment.runtime]], '目标运行时尚未固定镜像')
    if spec.environment.recipe:
        require(all(toolchain['images'].get(k) for k in ('gmah-api','gmah-web','gmah-redis','gmah-postgres')), 'GMAH 依赖镜像尚未准备或固定')
    engines=list(dict.fromkeys(c['engine'] for c in cases))
    generated={}
    if set(engines)&{'module','api'}:
        generated['test_generated.py']='from acceptance_support import run_case\n\n'+''.join(
            f"def {c['name']}():\n    run_case({c['id']!r})\n\n" for c in cases if c['engine'] in {'module','api'})
    if 'browser' in engines:
        require(toolchain['playwright'],'尚未安装 Playwright')
        generated['generated.spec.cjs']="const {test,expect}=require(process.env.ACCEPTANCE_PLAYWRIGHT);\nconst {runCase}=require('./browser-support.cjs');\n"+''.join(
            f"test({json.dumps(c['name'])},async ({{page}},info)=>runCase(page,expect,info,{json.dumps(c['id'])}));\n" for c in cases if c['engine']=='browser')
        generated['playwright.config.cjs']="module.exports={testDir:'.',testMatch:'generated.spec.cjs',workers:1,retries:0,timeout:20000,reporter:[['junit',{outputFile:process.env.ACCEPTANCE_OUTPUT+'/report.xml'}]],use:{headless:true,trace:'retain-on-failure'},outputDir:process.env.ACCEPTANCE_OUTPUT+'/browser'};\n"
        if spec.environment.recipe:
            generated['playwright.config.cjs']=generated['playwright.config.cjs'].replace("trace:'retain-on-failure'","trace:'on'")
    # Schemathesis receives a frozen external contract, never a schema fetched from the target.
    for c in cases:
        if c['engine']=='openapi': generated[c['id']+'-openapi.json']=documents[c['contract']]['content']
    checks=[]
    for engine in engines:
        if engine=='openapi':
            checks += [dict(id='generated-'+c['id'].lower(),engine=engine,title=c['title'],case_ids=[c['id']]) for c in cases if c['engine']==engine]
        elif engine in {'module','api'}:
            checks.append(dict(id='generated-pytest',engine=engine,title='业务规则与接口用例',case_ids=[c['id'] for c in cases if c['engine']==engine]))
        else: checks.append(dict(id='generated-browser',engine=engine,title='页面流程用例',case_ids=[c['id'] for c in cases if c['engine']==engine]))
    stages=[dict(name='分析依据与设计用例',duration_ms=round((perf_counter()-start)*1000),detail=f'{len(documents)} 份依据、{len(coverage)} 项标准、{len(cases)} 个新用例')]
    plan=dict(id='design-'+uuid.uuid4().hex[:16],repository=str(root),name=spec.title,scope=spec.scope,
              specification=spec.model_dump(),documents=list(documents.values()),cases=cases,coverage=coverage,
              exclusions=omissions,blockers=blockers,checks=checks,generated=generated,manifest=rows,
              file_count=len(files),snapshot_digest=sha(encode(rows)),toolchain=toolchain,compiler_digest=compiler_digest(),
              stages=stages,planner=dict(kind='structured',label='契约与数据驱动生成；未调用语言模型'),
              file_exclusions=exclusions)
    if spec.environment.recipe=='gmah-v1':
        plan['recipe_files']={name:(ROOT/name).read_text() for name in (
            'acceptance/planning/gmah.py','acceptance/recipes/gmah/load.js','acceptance/recipes/gmah/recovery.py')}
    return plan


def save(store, plan):
    digest=sha(encode(plan)); directory=store.root/'designs'; directory.mkdir(exist_ok=True)
    path=directory/(plan['id']+'.json'); require(not path.exists(),'计划编号已存在')
    path.write_bytes(encode(dict(record=plan,sha256=digest)))
    return {**plan,'digest':digest,'ready':not plan['blockers'] and bool(plan['cases'])}


def read(store, plan_id):
    require(re.fullmatch(r'design-[a-f0-9]{16}',plan_id),'无效验收方案')
    path=store.root/'designs'/(plan_id+'.json'); require(not path.is_symlink(),'方案路径非法')
    data=json.loads(path.read_bytes()); plan=data['record']
    require(plan['id']==plan_id and sha(encode(plan))==data['sha256'],'验收方案摘要不一致')
    return plan,data['sha256']
