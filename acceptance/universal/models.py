from typing import Any,Literal
from pydantic import Field,model_validator
from ..planning.models import Strict,ID,route
from .scenarios import Scenario
from .journeys import Journey


class Case(Strict):
    id: ID
    title: str = Field(min_length=1,max_length=200)
    unit: str
    kind: Literal['module','cli','http','browser','scenario','journey']
    flow: Scenario | None = None
    journey: Journey | None = None
    requires: list[str] = Field(default_factory=list)
    entry: str | None = None
    module: str | None = None
    function: str | None = None
    args: list[Any] = Field(default_factory=list,max_length=30)
    kwargs: dict[str,Any] = Field(default_factory=dict)
    argv: list[str] = Field(default_factory=list,max_length=30)
    stdin: str = Field(default='',max_length=20000)
    expected: Any
    comparison: Literal['equals','one_of','contains','text','json_stream','json_schema','exit_code'] = 'equals'
    exit_code: int | None = Field(default=None,ge=0,le=255)
    method: Literal['GET','POST','PUT','PATCH','DELETE','HEAD'] = 'GET'
    path: str = '/'
    body: Any = None
    status: int = Field(default=200,ge=100,le=599)
    pointer: str = ''
    selector: str | None = Field(default=None,max_length=500)

    @model_validator(mode='after')
    def valid(self):
        if (self.kind=='scenario') != (self.flow is not None):raise ValueError('状态流程用例必须提供flow，其他协议不得混入flow')
        if (self.kind=='journey') != (self.journey is not None):raise ValueError('journey协议必须提供journey，其他协议不得混入')
        if self.kind=='journey' and (self.expected is not None or self.comparison!='equals'):raise ValueError('journey的预期必须放在各个浏览器断言中，顶层expected=null')
        if self.kind=='module' and not (self.module and self.function):raise ValueError('模块用例缺少公开入口')
        if self.kind in {'http','browser'}:route(self.path)
        if self.kind=='browser' and not self.selector:raise ValueError('浏览器用例需要明确的断言定位器')
        if self.comparison=='contains' and self.expected in ('',[],{},None):raise ValueError('包含断言不能为空')
        if any('\0' in a or len(a)>2000 for a in self.argv):raise ValueError('参数无效或过长')
        return self


class Requirement(Strict):
    id: ID
    title: str = Field(min_length=1,max_length=200)
    source: ID
    quote: str = Field(min_length=5,max_length=4000)
    disposition: Literal['required','unresolved','excluded'] = 'required'
    reason: str = Field(default='',max_length=2000)
    gap_category: Literal['basis','environment','platform'] | None = None
    cases: list[Case] = Field(default_factory=list,max_length=12)

    @model_validator(mode='after')
    def covered(self):
        if self.disposition=='required' and not self.cases:raise ValueError('需求未设计用例')
        if self.disposition!='required' and (not self.reason or self.cases):raise ValueError('未决和排除项需说明原因且无用例')
        return self


class Proposal(Strict):
    requirements: list[Any] = Field(min_length=1,max_length=40)


def output_schema(document_ids=None):
    # Rows are validated independently after generation so one bad row cannot
    # erase valid rows. The model still sees the complete strict row schema.
    row=Requirement.model_json_schema();definitions=row.pop('$defs',{})
    if document_ids is not None:row['properties']['source']['enum']=list(document_ids)
    return {'type':'object','$defs':definitions,'properties':{'requirements':dict(type='array',minItems=1,maxItems=40,items=row)},'required':['requirements']}
