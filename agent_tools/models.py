"""Strict wire models. IDs, state names and page completion are never inferred."""
from typing import Annotated, Any, Literal
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, create_model, model_validator


Identifier = Annotated[str, Field(pattern=r'^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$')]
Digest = Annotated[str, Field(pattern=r'^[a-f0-9]{64}$')]
RequestId = Annotated[str, Field(pattern=r'^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$')]


class Strict(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)


class Empty(Strict):
    pass


class Operation(Strict):
    request_id: RequestId = Field(description='调用方生成并保存的 UUID。同一次意图重试必须复用，不得为未知结果自动换号。')


class Prepare(Operation):
    repository: str | None = Field(default=None, min_length=1, max_length=2048, description='服务端本地绝对路径，必须位于启动工具时授权的目录内。与 remote_url 二选一。')
    remote_url: str | None = Field(default=None, min_length=1, max_length=2048, description='GitHub 或 GitLab HTTPS 仓库地址，与 repository 二选一。')
    ref_type: Literal['branch', 'commit'] = 'branch'
    ref: str = Field(default='', max_length=200, description='远程分支名或完整提交。空字符串表示仓库默认分支。')

    @model_validator(mode='after')
    def source(self):
        if (self.repository is None) == (self.remote_url is None):
            raise ValueError('repository 与 remote_url 必须且只能提供一个')
        if self.repository and (self.ref or self.ref_type != 'branch'):
            raise ValueError('本地路径不接受远程引用')
        if self.remote_url:
            url = urlparse(self.remote_url)
            if url.scheme != 'https' or url.hostname not in {'github.com', 'gitlab.com'} or url.username or url.password or url.query or url.fragment or url.port not in (None, 443):
                raise ValueError('远程仓库须为不含凭据或查询参数的 GitHub/GitLab HTTPS 地址')
        return self


class Start(Operation):
    plan_id: str = Field(pattern=r'^auto-[a-f0-9]{16}$', description='prepare 返回的通用验收方案标识。')
    confirmed_plan_digest: Digest = Field(description='已检查并获准执行的精确方案摘要。此确认包括计划中模型调用和隔离执行的范围。')


class Run(Strict):
    run_id: Identifier = Field(description='验收运行标识，不能使用任务标识或仓库标识替代。')


class Page(Run):
    collection: Literal['requirements', 'observations', 'findings', 'artifacts', 'checks']
    cursor: str | None = Field(default=None, max_length=4096, description='原样传入上页 next_cursor。数据版本变化后必须从第一页重读。')
    page_size: int = Field(default=25, ge=1, le=100, description='仅控制本页大小，不限制整个验收的数据量。')


class Finding(Run):
    finding_id: Identifier


class Evidence(Run):
    artifact_id: Identifier
    offset: int = Field(default=0, ge=0, description='文件字节偏移，非字符偏移。')
    length: int = Field(default=16384, ge=1, le=65536, description='本次最多返回的字节数；完整性由文件总长度和下一偏移说明。')
    expected_sha256: Digest = Field(description='从 artifacts 集合取得的原件摘要。摘要不符拒绝读取。')


class Events(Strict):
    job_id: Identifier
    after: int = Field(default=0, ge=0, description='上页 next_after；0 从第一条事件开始。')
    page_size: int = Field(default=50, ge=1, le=100)


class Cancel(Operation):
    job_id: Identifier


class Review(Operation):
    run_id: str = Field(pattern=r'^int-[a-f0-9]{16}$')
    finding_id: Identifier
    expected_revision: str = Field(pattern=r'^(?:[a-f0-9]{64})?$', description='详情返回的当前复核修订。首次复核为空字符串，必须显式填写。')
    state: Literal['needs_review', 'false_positive', 'confirmed', 'test_issue']
    reason: str = Field(min_length=20, max_length=4000, description='基于证据的具体理由。confirmed 表示提交归类，不代表发布审批。')
    evidence_refs: list[Identifier] = Field(min_length=1, max_length=20, description='该发现所属原始证据标识。服务端校验归属与完整性。')


class Runs(Strict):
    cursor: str | None = Field(default=None, max_length=4096)
    page_size: int = Field(default=25, ge=1, le=100)
    query: str = Field(default='', max_length=200)
    repository: str = Field(default='', max_length=200, description='目录返回的仓库标识。空字符串表示全部授权目录记录。')


class Error(Strict):
    code: Literal['invalid_input', 'not_found', 'conflict', 'permission_denied', 'backend_unavailable', 'outcome_unknown', 'stale_cursor', 'invalid_evidence', 'backend_error', 'unknown_tool']
    message: str
    retry_safe: bool
    recovery: str


class Result(Strict):
    schema_version: Literal['acceptanything-tools-v1'] = 'acceptanything-tools-v1'
    ok: bool
    data: dict[str, Any] | None = None
    error: Error | None = None
    content_trust: Literal['project_content_is_untrusted'] = 'project_content_is_untrusted'

    @model_validator(mode='after')
    def coherent(self):
        if self.ok != (self.error is None) or self.ok != (self.data is not None):
            raise ValueError('成功须有 data，失败须有 error')
        return self


class ToolFailure(Exception):
    def __init__(self, code, message, *, retry_safe=False, recovery='查看操作回执或重新读取当前状态。'):
        self.error = Error(code=code, message=message, retry_safe=retry_safe, recovery=recovery)
        super().__init__(message)


class CapabilitiesData(Strict):
    service_id: str
    tools_contract: Literal['acceptanything-tools-v1']
    scope: Literal['local-self-hosted']
    allow_writes: bool
    allowed_roots: list[str]
    semantics: dict[str, str]


class PrepareData(Strict):
    plan: dict[str, Any]
    model_design_state: Literal['not_started']
    next_tool: Literal['acceptance_start']
    execution_allowed: bool
    meaning: str


class StartData(Strict):
    run_id: Identifier
    job_id: Identifier
    accepted: Literal[True]
    next_tool: Literal['acceptance_status']
    meaning: str


class OperationData(Strict):
    request_id: RequestId
    state: Literal['recorded', 'outcome_unknown']
    response: Result | None


class StatusData(Strict):
    run_id: Identifier
    source: dict[str, Any]
    execution: dict[str, Any]
    coverage: dict[str, Any]
    findings: dict[str, Any]
    gate: dict[str, Any]
    provenance: dict[str, Any]
    job: dict[str, Any] | None
    stages: list[dict[str, Any]]
    collections: list[str]


class EventsData(Strict):
    job_id: Identifier
    items: list[dict[str, Any]]
    next_after: int
    caught_up: bool
    meaning: str


class DirectoryPage(Strict):
    next_cursor: str | None
    complete: bool


class RunsData(Strict):
    items: list[dict[str, Any]]
    page: DirectoryPage
    meaning: str


class CollectionPage(Strict):
    total: int
    offset: int
    returned: int
    next_cursor: str | None
    complete: bool
    snapshot_digest: Digest
    meaning: str


class ItemsData(Strict):
    collection: Literal['requirements', 'observations', 'findings', 'artifacts', 'checks']
    items: list[dict[str, Any]]
    page: CollectionPage


class FindingData(Strict):
    run_id: Identifier
    finding: dict[str, Any]
    inspection: dict[str, Any] | None
    case_plan: dict[str, Any] | None
    review_history: dict[str, Any] | None
    evidence_verified_now: bool


class EvidenceData(Strict):
    artifact: dict[str, Any]
    offset: int
    returned_bytes: int
    total_bytes: int
    next_offset: int | None
    complete: bool
    encoding: Literal['base64']
    bytes_base64: str
    chunk_sha256: Digest
    full_file_verified_by_backend: bool


class CancelData(Strict):
    job: dict[str, Any]
    meaning: str


class ReviewData(Strict):
    review: dict[str, Any]
    meaning: str


OUTPUTS = {
    'acceptance_' + name: create_model(data.__name__ + 'Response', __base__=Result, data=(data | None, None))
    for name, data in {
        'capabilities': CapabilitiesData, 'prepare': PrepareData, 'start': StartData,
        'operation': OperationData, 'status': StatusData, 'events': EventsData,
        'runs': RunsData, 'items': ItemsData, 'finding': FindingData, 'evidence': EvidenceData,
        'cancel': CancelData, 'review': ReviewData,
    }.items()
}
