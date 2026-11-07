"""Server-only model connection settings; credentials stay in a separate file."""
import json
import os
from pathlib import Path
from urllib.parse import urlparse
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator


class Connection(BaseModel):
    model_config = ConfigDict(extra='forbid')
    base_url: str = ''
    model: str = ''
    provider: Literal['compatible','chat2api','deepseek'] = 'compatible'
    reasoning_effort: Literal['low','medium','high','xhigh'] | None = None
    key_file: str | None = None
    key_field: str | None = Field(default=None,pattern=r'^[A-Z][A-Z0-9_]{0,80}$')
    audit_file: str | None = None
    timeout_seconds: int = Field(default=600, ge=30, le=3900)

    @model_validator(mode='after')
    def valid(self):
        if self.base_url:
            url=urlparse(self.base_url)
            if not ((url.scheme=='https' or (url.scheme=='http' and url.hostname in {'127.0.0.1','localhost'}))
                    and url.hostname and not url.username and not url.password and not url.query and not url.fragment):
                raise ValueError('模型连接需要 HTTPS 或本机地址，且不含凭据或查询参数')
        if self.provider=='chat2api' and (self.model!='gpt-6-thinking' or self.reasoning_effort!='high'):
            raise ValueError('本项目 Chat2API 接入固定使用 gpt-6-thinking + high')
        if self.provider=='deepseek':
            if self.base_url.rstrip('/') not in {'https://api.deepseek.com','https://api.deepseek.com/v1'}:
                raise ValueError('DeepSeek 官方接入仅允许 api.deepseek.com 的 HTTPS 接口')
            if self.model!='deepseek-flash' or self.reasoning_effort!='high' or not self.key_file:
                raise ValueError('DeepSeek 接入需要 deepseek-flash、high 和服务端密钥文件')
        if self.key_field and not self.key_file:
            raise ValueError('命名密钥字段需要配置本机文件')
        return self


def load():
    path=os.getenv('ACCEPTANCE_PLANNER_CONFIG_FILE')
    data=json.loads(Path(path).expanduser().read_text()) if path else {}
    for field,env in (
        ('base_url','ACCEPTANCE_PLANNER_BASE_URL'),('model','ACCEPTANCE_PLANNER_MODEL'),
        ('key_file','ACCEPTANCE_PLANNER_KEY_FILE'),('reasoning_effort','ACCEPTANCE_PLANNER_REASONING_EFFORT'),
        ('provider','ACCEPTANCE_PLANNER_PROVIDER'),('timeout_seconds','ACCEPTANCE_PLANNER_TIMEOUT_SECONDS')):
        if env in os.environ:data[field]=os.environ[env]
    return Connection.model_validate(data)
