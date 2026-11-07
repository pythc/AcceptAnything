from __future__ import annotations
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class Context(Strict):
    repository: str = Field(min_length=1, max_length=2048)
    revision: str = Field(min_length=1, max_length=160)
    snapshot_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    environment: str = Field(min_length=1, max_length=160)
    scope: str = Field(min_length=1, max_length=2048)


class Rule(Strict):
    id: str = Field(pattern=r"^[a-zA-Z0-9_-]{1,64}$")
    kind: Literal[
        "metric", "delta", "new-findings", "licenses", "required-tests", "environments"
    ]
    tasks: list[str] = Field(min_length=1 )
    metric: str | None = None
    operator: Literal["le", "ge", "eq"] = "le"
    threshold: float = 0
    reduction: Literal["sum", "min", "max"] = "sum"
    values: list[str] = Field(default_factory=list, max_length=1000)

    @model_validator(mode="after")
    def operands(self):
        if self.kind in {"metric", "delta"} and not self.metric:
            raise ValueError("指标规则必须指定 metric")
        if (
            self.kind in {"licenses", "required-tests", "environments"}
            and not self.values
        ):
            raise ValueError("集合规则必须指定 values")
        return self


class Exclusion(Strict):
    subject: str = Field(min_length=1)
    reason: str = Field(min_length=1)


class Task(Strict):
    id: str = Field(pattern=r"^[a-z][a-z0-9-]{0,63}$")
    tool: str = Field(min_length=1)
    target: str = "."
    timeout: int = Field(default=120, ge=1)
    network: Literal["none", "registry"] = "none"
    service_script: str | None = None

    @field_validator("target", "service_script")
    @classmethod
    def safe_target(cls, value):
        if value is None:
            return value
        from pathlib import PurePosixPath

        p = PurePosixPath(value)
        if value != "." and (
            p.is_absolute()
            or ".." in p.parts
            or str(p) != value
            or value.startswith("-")
            or "\\" in value
        ):
            raise ValueError("需要规范相对路径")
        return value


class Profile(Strict):
    id: str = Field(pattern=r"^[a-z][a-z0-9-]{0,63}$")
    name: str = Field(min_length=1 )
    repository: str = Field(min_length=1)
    version: str = Field(min_length=1)
    environment: str = Field(min_length=1)
    scope: str = Field(min_length=1)
    files: list[str] = Field(min_length=1)
    tasks: list[Task] = Field(min_length=1 )
    rules: list[Rule] = Field(min_length=1 )
    exclusions: list[Exclusion] = Field(default_factory=list)
    baseline: str | None = Field(default=None, pattern=r"^int-[a-f0-9]{16}$")

    @model_validator(mode="after")
    def unique(self):
        for values in (
            [x.id for x in self.tasks],
            [x.id for x in self.rules],
            self.files,
        ):
            if len(values) != len(set(values)):
                raise ValueError("重复身份或文件")
        ids = {x.id for x in self.tasks}
        if any(not set(r.tasks) <= ids for r in self.rules):
            raise ValueError("门禁引用未计划任务")
        # Every executed task must be governed by at least one explicit acceptance rule.
        if set().union(*(set(r.tasks) for r in self.rules)) != ids:
            raise ValueError("有任务未配置门禁规则")
        return self
