"""Portable project acceptance configuration, compiled by existing test engines.

The configuration defines a reviewed scope, not a claim of entire-product coverage.
Service startup is constrained by Environment; it cannot supply host commands.
"""
import json
from pathlib import Path
from typing import Literal
from pydantic import Field, field_validator
from .planning.models import Specification, DesignInput, Document, relative
from .integrations.models import Strict, Task, Rule, Exclusion, Profile
from .integrations.discovery import inventory
from .integrations.formats import require
from .integrations.runner import sha, encode
from .planning import service, compiler


class Basis(Strict):
    id: str = Field(pattern=r'^[A-Za-z][A-Za-z0-9_-]{0,63}$')
    path: str
    excerpt: str | None = Field(default=None,min_length=5,max_length=200000)
    title: str | None = Field(default=None,max_length=200)
    anchor: str = Field(default='',max_length=200)
    _relative=field_validator('path')(relative)


class ProjectConfig(Strict):
    schema_version: Literal[1]
    documents: list[Basis] = Field(min_length=1)
    specification: Specification
    include_scanners: bool = True
    tasks: list[Task] = Field(default_factory=list)
    rules: list[Rule] = Field(default_factory=list)
    exclusions: list[Exclusion] = Field(default_factory=list)
    # Generated model proposals must already have been reviewed via Test Design.
    draft_id: str | None = Field(default=None,pattern=r'^draft-[a-f0-9]{16}$')
    draft_ids: list[str] = Field(default_factory=list)


def prepare(store,repository,configuration=None,*,remote_source=None,repository_binding=None):
    root,files,_=inventory(repository)
    path=Path(configuration).expanduser().resolve() if configuration else root/'acceptance.project.json'
    require(path.is_file(),'项目配置不存在')
    raw=path.read_bytes();config=ProjectConfig.model_validate_json(raw)
    documents=[]
    for basis in config.documents:
        require(basis.path in files,'验收依据必须位于本次仓库冻结范围：'+basis.path)
        text=(root/basis.path).read_text()
        if basis.excerpt:
            require(basis.excerpt in text,'独立依据摘录已变化或不在原文中')
            text=basis.excerpt
        documents.append(Document(id=basis.id,title=basis.title or basis.path,origin=basis.path+basis.anchor,content=text))
    plan=service.prepare(store,DesignInput(repository=str(root),documents=documents,
        specification=config.specification,include_scanners=config.include_scanners,draft_id=config.draft_id,draft_ids=config.draft_ids),repository_binding=repository_binding)
    # service.prepare already froze a complete compiler input. Re-save as a new
    # plan identity after extending only reviewed registry tasks and explicit gates.
    plan.pop('digest',None);plan.pop('ready',None)
    profile=plan.get('profile')
    require(profile,'项目没有可执行检查')
    require(all(t.tool!='acceptance-generated' for t in config.tasks),'生成检查只能由可信编译器生成')
    profile['tasks'] += [t.model_dump() for t in config.tasks]
    profile['rules'] += [r.model_dump() for r in config.rules]
    profile['exclusions'] += [e.model_dump() for e in config.exclusions]
    profile['scope']=config.specification.scope
    plan['profile']=Profile.model_validate(profile).model_dump()
    # Register validates supported tools/targets without running repository code.
    store.register(plan['profile'])
    plan['checks'] += [dict(id=t.id,title=t.id,tool=t.tool,expected='满足配置中的冻结门禁') for t in config.tasks]
    plan['exclusions'] += [e.model_dump() for e in config.exclusions]
    plan['project_configuration']=dict(path=str(path),sha256=sha(raw),content=json.loads(raw),
        coverage='declared-scope',limitation='仅覆盖项目配置声明的需求与检查；未执行的性能、恢复或设备环境不计为通过')
    if remote_source:
        plan['remote_source']=remote_source
    import uuid
    plan['id']='design-'+uuid.uuid4().hex[:16]
    return compiler.save(store,plan)


def public(plan):
    result=dict(id=plan['id'],digest=plan['digest'],repository=plan['repository'],scope=plan['scope'],
        file_count=len(plan['manifest']),check_count=len(plan['checks']),ready=plan['ready'],
        snapshot_digest=plan['snapshot_digest'],documents=[d['origin'] for d in plan['documents']],
        blockers=[x['reason'] for x in plan['blockers']],exclusions=plan['exclusions'],kind='configured',
        stages=[dict(id='baseline',title='冻结依据与源码'),dict(id='cases',title='生成用例'),
                dict(id='L1',title='执行配置范围'),dict(id='gate',title='质量门禁')])
    if plan.get('remote_source'): result['remote_source']=plan['remote_source']
    if plan['specification']['environment'].get('recipe')=='gmah-v1':
        result['stages']=[dict(id=k,title=v) for k,v in [('baseline','冻结源码与依据'),('design','复用已确认的 GPT-6 High 中文用例'),
            ('scanners','代码与依赖扫描'),('api','模型 API 用例'),('browser','模型浏览器用例'),('build','生产构建与原有回归'),
            ('load','业务负载'),('recovery','重启与恢复'),('gate','清理核对与质量门禁')]]
    return result


def registered_configuration(repository):
    """Server-owned mapping; never infer a recipe from a similar folder name."""
    from .engine import ROOT
    path=ROOT/'var/project-configurations.json'
    if not path.is_file():return None
    return json.loads(path.read_text()).get(str(Path(repository).expanduser().resolve()))
