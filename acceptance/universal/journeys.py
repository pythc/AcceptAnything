"""Typed browser inputs. Public setup bindings and independent oracles stay separate."""
from typing import Any, Literal
from pydantic import Field, model_validator, ValidationInfo
from ..planning.models import Strict, ID, route
from .scenarios import Step, Scenario
import re


def validate_status_basis(journey,quote):
    for step in journey.steps:
        if step.action not in {'request','poll'} or step.pointer!='/status' or step.expected is None:continue
        values=[]
        def visit(value):
            if not isinstance(value,dict):return
            for key in ('const','minimum','maximum','exclusiveMinimum','exclusiveMaximum'):
                if key in value:values.append(value[key])
            values.extend(value.get('enum',[]))
            for key in ('allOf','anyOf','oneOf'):
                for child in value.get(key,[]):visit(child)
        if step.comparison=='json_schema':visit(step.expected)
        else:values.append(step.expected)
        for code in values:
            if type(code) is int and 100<=code<=599 and not re.search(r'(?<![0-9])'+str(code)+r'(?![0-9])',quote):raise ValueError('具体HTTP状态码 '+str(code)+' 缺少引用原文数值依据')


class BrowserStep(Strict):
    id: ID
    action: Literal['goto','fill','click','press','check','uncheck','select','dialog','expect_text','expect_visible','expect_hidden','expect_url','expect_value','expect_count','expect_attribute','expect_validity','request','poll']
    selector: str | None = None
    path: str = '/'
    value: Any = None
    expected: Any = None
    comparison: Literal['equals','contains','json_schema'] = 'equals'
    attribute: str | None = None
    method: Literal['GET','POST','PUT','PATCH','DELETE','HEAD'] = 'GET'
    form: dict[str,Any] | None = None
    body: Any = None
    headers: dict[str,str] = Field(default_factory=dict)
    pointer: str = ''
    capture: str | None = None
    timeout_ms: int = Field(default=10000,ge=1,le=120000)

    @model_validator(mode='after')
    def valid(self,info:ValidationInfo):
        version=(info.context or {}).get('protocol_version',19)
        if self.action not in {'goto','expect_url','request','poll','dialog'} and not self.selector:raise ValueError('浏览器动作需要CSS定位器')
        if self.action=='dialog' and self.value not in {'accept','dismiss'}:raise ValueError('对话框操作需为accept/dismiss')
        if self.action in {'goto','request','poll'}:route(self.path)
        if self.action=='expect_attribute' and not self.attribute:raise ValueError('属性断言需要attribute')
        if self.action in {'expect_text','expect_url','expect_value','expect_attribute'} and not isinstance(self.expected,str):raise ValueError('文本、地址与属性断言需要字符串预期')
        if self.action=='expect_count' and (type(self.expected) is not int or self.expected<0):raise ValueError('元素数量需要非负整数')
        if self.action=='expect_visible' and type(self.expected) is not bool:raise ValueError('可见性需要布尔预期')
        if self.action=='expect_hidden' and self.expected is not True:raise ValueError('隐藏断言需要expected=true')
        if self.action=='expect_validity' and (not isinstance(self.expected,dict) or not self.expected or set(self.expected)-{'valid','valueMissing','typeMismatch','rangeUnderflow','rangeOverflow'} or any(type(v) is not bool for v in self.expected.values())):raise ValueError('原生表单校验需要明确的布尔字段约束')
        if version<19 and self.action=='request' and self.expected is not None:raise ValueError('request只采集回执；请用poll进行独立断言，不能忽略expected')
        if self.comparison!='equals' and self.action not in ({'expect_text','poll','request'} if version>=19 else {'expect_text','poll'}):raise ValueError('该浏览器动作不支持所选比较方式')
        if self.action=='expect_text' and self.comparison not in {'equals','contains'}:raise ValueError('页面文本仅支持equals/contains')
        if self.action.startswith('expect_') or self.action=='poll':
            if self.expected is None:raise ValueError('浏览器断言需要独立预期值')
            if '${' in str(self.expected):raise ValueError('预期不能从实际响应捕获值插值得到')
        if self.comparison=='json_schema':
            from .scenarios import validate_schema
            validate_schema(self.expected)
        if self.capture and (not self.capture.isidentifier() or self.capture.startswith('_')):raise ValueError('捕获变量名称无效')
        if self.capture and self.action not in {'request','poll'}:raise ValueError('capture仅适用于HTTP回执')
        return self


class Journey(Strict):
    version: Literal[1] = 1
    setup: list[Step] = Field(min_length=1)
    cleanup: list[Step] = Field(default_factory=list)
    app: ID
    adapter: Literal['wsgi','asgi','node-listener']
    steps: list[BrowserStep] = Field(min_length=1)

    @model_validator(mode='after')
    def valid(self,info:ValidationInfo):
        # Reuse the public object/reference and callback validator. This dummy
        # check is validation scaffolding only; it never becomes an oracle.
        self.preparation()
        if self.app not in {s.id for s in self.setup}:raise ValueError('app必须引用准备步骤产生的真实应用')
        if len({s.id for s in self.steps})!=len(self.steps):raise ValueError('浏览器步骤编号重复')
        if not any(s.action.startswith('expect_') or s.action=='poll' for s in self.steps):raise ValueError('浏览器流程必须包含业务断言')
        if (info.context or {}).get('protocol_version',19)>=19:
            if not any(s.action=='goto' for s in self.steps):raise ValueError('浏览器流程必须真正导航页面；纯HTTP请使用接口流程')
            last=max([i for i,s in enumerate(self.steps) if s.action in {'fill','click','press','check','uncheck','select'}],default=-1)
            if not any(s.action.startswith('expect_') for s in self.steps[last+1:]):raise ValueError('最后一次页面操作后必须核对页面结果；不能只核对接口')
        return self

    def preparation(self):
        return Scenario(steps=self.setup,cleanup=self.cleanup,checks=[dict(step=self.setup[0].id,expected=None)])
