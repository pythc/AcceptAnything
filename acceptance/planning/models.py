"""A model may propose this data contract; only trusted compilers produce code."""
import re
from typing import Annotated, Any, Literal
from pathlib import PurePosixPath
from pydantic import Field, model_validator, field_validator
from ..integrations.models import Strict

ID = Annotated[str, Field(pattern=r'^[A-Za-z][A-Za-z0-9_-]{0,63}$')]
DIMENSIONS = ('normal', 'boundary', 'error', 'permission', 'state', 'persistence', 'performance', 'recovery')


def relative(value):
    p = PurePosixPath(value)
    if not value or p.is_absolute() or '..' in p.parts or str(p) != value or '\\' in value or value.startswith('-'):
        raise ValueError('需要仓库内规范相对文件路径')
    return value


def route(value):
    if not value.startswith('/') or value.startswith('//') or any(c in value for c in ('\\', '\r', '\n', '#')):
        raise ValueError('只接受以单斜杠开头的目标内路径')
    return value


class Document(Strict):
    id: ID
    title: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1, max_length=200_000)
    origin: str = Field(default='用户提供', max_length=2048)


class Assertion(Strict):
    pointer: str = Field(default='', max_length=500)
    operator: Literal['equals', 'contains', 'schema'] = 'equals'
    value: Any

    @field_validator('pointer')
    @classmethod
    def pointer_syntax(cls, value):
        if value and (not value.startswith('/') or re.search(r'~(?![01])', value)):
            raise ValueError('断言路径必须是 JSON Pointer')
        return value


class Call(Strict):
    kind: Literal['call']
    module: str
    function: str = Field(pattern=r'^[A-Za-z_$][A-Za-z0-9_$]{0,120}$')
    args: list[Any] = Field(default_factory=list, max_length=20)
    assertions: list[Assertion] = Field(min_length=1, max_length=20)

    _relative = field_validator('module')(relative)


class Http(Strict):
    kind: Literal['http']
    method: Literal['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'HEAD'] = 'GET'
    path: str = Field(max_length=2000)
    body: Any = None
    headers: dict[str, str] = Field(default_factory=dict, max_length=20)
    status: int = Field(ge=100, le=599)
    assertions: list[Assertion] = Field(default_factory=list, max_length=20)
    capture: dict[ID, str] = Field(default_factory=dict, max_length=20)
    _route = field_validator('path')(route)

    @model_validator(mode='after')
    def safe_headers(self):
        for key, value in self.headers.items():
            if not re.fullmatch(r'[A-Za-z0-9-]+', key) or key.lower() in {'host','connection','content-length','transfer-encoding'} or '\r' in value or '\n' in value:
                raise ValueError('请求头无效或会改变目标边界')
        for value in self.capture.values():
            Assertion.pointer_syntax(value)
        return self


class Browser(Strict):
    kind: Literal['goto', 'fill', 'click', 'check', 'expect_text', 'expect_visible', 'expect_url']
    selector: str = Field(default='', max_length=500)
    value: str = Field(default='', max_length=2000)

    @model_validator(mode='after')
    def fields(self):
        if self.kind in {'goto', 'expect_url'}:
            route(self.value)
        elif not self.selector:
            raise ValueError('页面操作缺少定位器')
        return self


Step = Annotated[Call | Http | Browser, Field(discriminator='kind')]


class Boundary(Strict):
    variable: ID
    minimum: float
    maximum: float
    step: float = Field(default=1, gt=0)
    valid: Any = True
    invalid: Any = False

    @model_validator(mode='after')
    def limits(self):
        if self.minimum >= self.maximum or self.step > self.maximum - self.minimum:
            raise ValueError('边界区间或步长无效')
        return self


class Scenario(Strict):
    id: ID
    title: str = Field(min_length=1, max_length=200)
    dimension: Literal['normal','boundary','error','permission','state','persistence','performance','recovery']
    engine: Literal['module', 'api', 'browser', 'openapi']
    steps: list[Step] = Field(default_factory=list, max_length=30)
    examples: list[dict[str, Any]] = Field(default_factory=list, max_length=100)
    matrix: dict[ID, list[Any]] = Field(default_factory=dict, max_length=6)
    boundary: Boundary | None = None
    contract: ID | None = None

    @model_validator(mode='after')
    def coherent(self):
        if self.dimension in {'performance','recovery'}:
            raise ValueError('性能与恢复需要负载/恢复环境配方；当前生成器不把普通请求冒充性能或恢复验收')
        if sum(bool(x) for x in (self.examples, self.matrix, self.boundary)) > 1:
            raise ValueError('每个场景选择数据表、矩阵或边界中的一种')
        if any(not 1 <= len(x) <= 30 for x in self.matrix.values()):
            raise ValueError('矩阵轴需要 1–30 个值')
        if self.engine == 'openapi':
            if not self.contract or self.steps or self.examples or self.matrix or self.boundary:
                raise ValueError('OpenAPI 场景仅接受契约文档引用')
        else:
            if not self.steps or self.contract:
                raise ValueError('场景需要可执行步骤')
            kinds = {s.kind for s in self.steps}
            if self.engine == 'module' and kinds != {'call'}:
                raise ValueError('模块场景只接受函数调用')
            if self.engine == 'api' and kinds != {'http'}:
                raise ValueError('接口场景只接受 HTTP 步骤')
            if self.engine == 'browser' and (kinds & {'call'} or not any(k.startswith('expect_') for k in kinds)):
                raise ValueError('页面场景需要独立页面断言')
            if self.engine == 'browser' and any(a.operator=='schema' for step in self.steps if isinstance(step,Http) for a in step.assertions):
                raise ValueError('页面联合流程的接口断言支持 equals/contains；JSON Schema 请使用独立 API 场景')
        return self


class Requirement(Strict):
    id: ID
    title: str = Field(min_length=1, max_length=200)
    source: ID
    quote: str = Field(min_length=5, max_length=10000)
    priority: Literal['P0', 'P1', 'P2', 'P3'] = 'P2'
    disposition: Literal['required','excluded','unresolved'] = 'required'
    reason: str = Field(default='', max_length=2000)
    scenarios: list[Scenario] = Field(default_factory=list, max_length=40)

    @model_validator(mode='after')
    def coverage(self):
        if self.disposition == 'required' and not self.scenarios:
            raise ValueError('必验标准必须设计至少一个场景；未设计的标为 unresolved')
        if self.disposition != 'required' and (not self.reason or self.scenarios):
            raise ValueError('排除或待确认标准需要原因，且不产生用例')
        return self


class Environment(Strict):
    mode: Literal['module','service','cli'] = 'module'
    runtime: Literal['node','python','go'] = 'node'
    entrypoint: str | None = None
    port: int = Field(default=19300, ge=1024, le=65535)
    ready_path: str = '/health'
    recipe: Literal['gmah-v1'] | None = None
    _route = field_validator('ready_path')(route)

    @model_validator(mode='after')
    def launch(self):
        if self.recipe and (self.mode != 'service' or self.runtime != 'python' or self.entrypoint != 'src/agent_workflow/api/app.py'):
            raise ValueError('GMAH 配方仅适用于已登记的 Python 服务入口')
        if self.mode in {'service','cli'}:
            if not self.entrypoint:
                raise ValueError('服务验收需要入口脚本')
            relative(self.entrypoint)
        elif self.entrypoint is not None:
            raise ValueError('模块验收不接受服务入口')
        return self


class Specification(Strict):
    title: str = Field(min_length=1, max_length=200)
    scope: str = Field(min_length=1, max_length=2000)
    environment: Environment = Field(default_factory=Environment)
    requirements: list[Requirement] = Field(min_length=1, max_length=100)

    @model_validator(mode='after')
    def identifiers(self):
        if self.environment.mode=='cli' or self.environment.runtime=='go':raise ValueError('CLI 需要通用命令行方案契约')
        ids = [r.id for r in self.requirements]
        scenarios = [s.id for r in self.requirements for s in r.scenarios]
        if len(set(ids)) != len(ids) or len(set(scenarios)) != len(scenarios):
            raise ValueError('标准或场景编号重复')
        engines = {s.engine for r in self.requirements for s in r.scenarios}
        if (self.environment.mode == 'module' and engines - {'module'}) or (self.environment.mode == 'service' and 'module' in engines):
            raise ValueError('场景与目标运行方式不一致；分别设计模块与服务验收')
        return self


class DesignInput(Strict):
    repository: str = Field(min_length=1, max_length=2048)
    documents: list[Document] = Field(min_length=1, max_length=20)
    specification: Specification
    include_scanners: bool = True
    draft_id: str | None = Field(default=None, pattern=r'^draft-[a-f0-9]{16}$')
    draft_ids: list[Annotated[str,Field(pattern=r'^draft-[a-f0-9]{16}$')]] = Field(default_factory=list,max_length=8)

    @model_validator(mode='after')
    def drafts(self):
        if self.draft_id and self.draft_ids or len(set(self.draft_ids))!=len(self.draft_ids):
            raise ValueError('模型草稿重复或同时选择单批与多批')
        return self


class ModuleScenario(Scenario):
    dimension: Literal['normal','boundary','error','permission','state','persistence']
    engine: Literal['module']
    steps: list[Call] = Field(min_length=1,max_length=30)


class ModuleRequirement(Requirement):
    scenarios: list[ModuleScenario] = Field(default_factory=list,max_length=40)


class ModuleSpecification(Specification):
    requirements: list[ModuleRequirement] = Field(min_length=1,max_length=100)


class ServiceScenario(Scenario):
    dimension: Literal['normal','boundary','error','permission','state','persistence']
    engine: Literal['api','browser','openapi']
    steps: list[Annotated[Http | Browser, Field(discriminator='kind')]] = Field(default_factory=list,max_length=30)


class ServiceRequirement(Requirement):
    scenarios: list[ServiceScenario] = Field(default_factory=list,max_length=40)


class ServiceSpecification(Specification):
    requirements: list[ServiceRequirement] = Field(min_length=1,max_length=100)


class CallBinding(Strict):
    module: str
    function: str = Field(pattern=r'^[A-Za-z_$][A-Za-z0-9_$]{0,120}$')
    args: list[Any] = Field(default_factory=list,max_length=20)
    result_pointers: list[str] = Field(default_factory=lambda:[''],max_length=20)
    _relative = field_validator('module')(relative)

    @field_validator('result_pointers')
    @classmethod
    def pointers(cls,values):
        for value in values:Assertion.pointer_syntax(value)
        return values


class DecisionRow(Strict):
    inputs: dict[str,Any] = Field(max_length=20)
    expected: Any
    title: str = Field(default='生成用例',max_length=200)
    dimension: Literal['normal','boundary','error','permission','state','persistence'] = 'normal'
    rationale: str = Field(default='',max_length=1000)
    basis_quote: str = Field(default='',max_length=10000)


class DecisionTable(Strict):
    rows: list[DecisionRow] = Field(min_length=1,max_length=12)


class TableTarget(Strict):
    id: ID
    title: str = Field(max_length=200)
    source: ID
    quote: str = Field(min_length=5,max_length=10000)
    priority: Literal['P0','P1','P2','P3'] = 'P2'
    call: Call
    input_examples: list[dict[str,Any]] = Field(max_length=3)
    result_schema: dict[str,Any]
    input_schema: dict[str,Any] = Field(default_factory=dict)
    precondition: str = Field(default='',max_length=2000)
    require_chinese: bool = False

    @model_validator(mode='after')
    def scalar_adapter(self):
        if len(self.call.assertions)!=1 or self.call.assertions[0].pointer or self.call.assertions[0].operator!='equals' or self.call.assertions[0].value!='${expected}':
            raise ValueError('决策表适配器仅接受独立标量预期占位符')
        return self


class ServiceTableTarget(Strict):
    id: ID
    title: str = Field(max_length=200)
    source: ID
    quote: str = Field(min_length=5,max_length=10000)
    priority: Literal['P0','P1','P2','P3'] = 'P2'
    engine: Literal['api','browser']
    steps: list[Annotated[Http | Browser,Field(discriminator='kind')]] = Field(min_length=1,max_length=30)
    input_schema: dict[str,Any]
    result_schema: dict[str,Any]
    precondition: str = Field(max_length=2000)
    require_chinese: Literal[True] = True

    @model_validator(mode='after')
    def workflow(self):
        Scenario(id='shape',title='流程形状',dimension='normal',engine=self.engine,steps=self.steps)
        import json
        asserted=False
        for step in self.steps:
            data=step.model_dump()
            values=[a.value for a in step.assertions] if isinstance(step,Http) else ([step.value] if step.kind in {'expect_text','expect_url'} else [])
            asserted |= any('${expected}' in json.dumps(v,ensure_ascii=False) for v in values)
            if isinstance(step,Http): data.pop('assertions')
            elif step.kind in {'expect_text','expect_url'}: data.pop('value')
            if '${expected}' in json.dumps(data,ensure_ascii=False):
                raise ValueError('模型预期只能用于断言，不能写入请求或定位器')
            if isinstance(step,Http) and 'expected' in step.capture:
                raise ValueError('响应捕获不能覆盖模型预期')
        if not asserted: raise ValueError('流程必须实际断言模型预期')
        return self


class DraftInput(Strict):
    repository: str = Field(min_length=1, max_length=2048)
    documents: list[Document] = Field(min_length=1)
    scope: str = Field(min_length=1, max_length=2000)
    environment: Environment = Field(default_factory=Environment)
    call_bindings: list[CallBinding] = Field(default_factory=list,max_length=100)
    table_target: TableTarget | None = None
    service_table_target: ServiceTableTarget | None = None
    automatic_target: dict[str, Any] | None = None
    universal_target: dict[str, Any] | None = None

    @model_validator(mode='after')
    def single_projection(self):
        if not self.universal_target and len(self.documents)>20:raise ValueError('手动设计每批最多20份文档')
        if sum(bool(x) for x in (self.table_target,self.service_table_target,self.automatic_target,self.universal_target))>1:
            raise ValueError('一次生成只选择一种决策表')
        if self.service_table_target and self.environment.mode!='service':
            raise ValueError('服务决策表需要服务环境')
        return self


class CliCase(Strict):
    id: ID
    title: str = Field(min_length=1,max_length=200)
    dimension: Literal['normal','boundary','error','state']
    rationale: str = Field(min_length=5,max_length=1200)
    argv: list[str] = Field(default_factory=list,max_length=30)
    stdin: str = Field(default='',max_length=20000)
    comparison: Literal['json_stream','text','contains'] = 'json_stream'
    stdout: str = Field(default='',max_length=20000)
    stderr_contains: str = Field(default='',max_length=2000)
    exit_code: int | None = Field(default=0,ge=0,le=255)

    @model_validator(mode='after')
    def executable(self):
        if not self.stdout and not self.stderr_contains: raise ValueError('用例没有独立输出预期')
        if self.comparison=='contains' and not self.stdout.strip() and not self.stderr_contains.strip():raise ValueError('包含断言不能为空白')
        if any(len(a)>2000 or '\x00' in a for a in self.argv):raise ValueError('命令参数超限或无效')
        if self.comparison=='json_stream' and self.stdout:
            import json
            decoder=json.JSONDecoder();remaining=self.stdout.strip()
            while remaining:
                _,end=decoder.raw_decode(remaining);remaining=remaining[end:].strip()
        return self


class CliRequirement(Strict):
    id: ID
    title: str = Field(min_length=1,max_length=200)
    source: ID
    quote: str = Field(min_length=5,max_length=10000)
    disposition: Literal['required','excluded','unresolved'] = 'required'
    reason: str = Field(default='',max_length=2000)
    scenarios: list[CliCase] = Field(default_factory=list,max_length=8)

    @model_validator(mode='after')
    def coverage(self):
        if self.disposition=='required' and not self.scenarios:raise ValueError('必验需求没有用例')
        if self.disposition!='required' and (not self.reason or self.scenarios):raise ValueError('未决或排除项需要原因且不能有用例')
        return self


class CliRow(CliCase):
    source: ID
    basis_quote: str = Field(min_length=5,max_length=1000)


class CliTable(Strict):
    rows: list[CliRow] = Field(min_length=4,max_length=8)


class CliSpecification(Strict):
    title: str = Field(min_length=1,max_length=200)
    scope: str = Field(min_length=1,max_length=2000)
    environment: Environment
    requirements: list[CliRequirement] = Field(min_length=1,max_length=12)

    @model_validator(mode='after')
    def identifiers(self):
        ids=[r.id for r in self.requirements];cases=[s.id for r in self.requirements for s in r.scenarios]
        if len(set(ids))!=len(ids) or len(set(cases))!=len(cases):raise ValueError('需求或用例编号重复')
        if not 4<=len(cases)<=8 and not (not cases and all(r.disposition!='required' for r in self.requirements)):raise ValueError('每批必须有4至8条有依据的用例，或明确列出未决依据')
        return self


class ExecuteInput(Strict):
    plan_id: str = Field(pattern=r'^design-[a-f0-9]{16}$')
    digest: str = Field(pattern=r'^[a-f0-9]{64}$')
