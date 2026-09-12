"""spec 0002 2.3: `AgentDefinition` — `agent_versions.definition` 의 내용(열린 질문 3, D-3).

pydantic 은 AR-9 의 금지 목록에 없습니다 — 프레임워크가 아니라 데이터 검증 라이브러리이고
`domain` 이 이미 이 모델을 위해 씁니다. api 는 요청 본문을 이 모델로 검증한 뒤 `jsonb` 로
저장하고, 이 모델의 JSON Schema 가 OpenAPI 에 실려 sdk 타입이 함께 생성됩니다(P1-1).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from aether_runtime.domain.tools import BUILTIN_TOOL_NAMES


class ModelRef(BaseModel):
    """`model.id` 가 `null` 이면 배포 설정 `AETHER_MODEL_ID` 를 씁니다."""

    id: str | None = None


class Backoff(BaseModel):
    base_seconds: float = 0.5
    max_seconds: float = 8.0

    @model_validator(mode="after")
    def _check_range(self) -> Backoff:
        if self.base_seconds <= 0:
            raise ValueError("policy.backoff.base_seconds must be > 0")
        if self.max_seconds < self.base_seconds:
            raise ValueError("policy.backoff.max_seconds must be >= policy.backoff.base_seconds")
        return self


class Policy(BaseModel):
    timeout_seconds: int = Field(default=120, ge=1, le=3600)
    max_steps: int = Field(default=8, ge=1, le=64)
    model_retries: int = Field(default=2, ge=0, le=10)
    tool_retries: int = Field(default=1, ge=0, le=10)
    backoff: Backoff = Field(default_factory=Backoff)


class AgentDefinition(BaseModel):
    """`schema_version` 을 올리는 것은 파괴적 변경 판정 대상입니다(DP-1)."""

    schema_version: Literal[1]
    system_prompt: str
    model: ModelRef = Field(default_factory=ModelRef)
    tools: list[str] = Field(default_factory=list)
    policy: Policy = Field(default_factory=Policy)

    @field_validator("system_prompt")
    @classmethod
    def _system_prompt_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("system_prompt must not be empty")
        return value

    @field_validator("tools")
    @classmethod
    def _tools_known_and_unique(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError("tools must not contain duplicates")
        unknown = sorted(set(value) - BUILTIN_TOOL_NAMES)
        if unknown:
            raise ValueError(f"unknown tools (outside BUILTIN_TOOL_NAMES): {unknown}")
        return value
