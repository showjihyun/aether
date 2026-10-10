"""spec 0002 2.3: `AgentDefinition` — `agent_versions.definition` 의 내용(열린 질문 3, D-3).

pydantic 은 AR-9 의 금지 목록에 없습니다 — 프레임워크가 아니라 데이터 검증 라이브러리이고
`domain` 이 이미 이 모델을 위해 씁니다. api 는 요청 본문을 이 모델로 검증한 뒤 `jsonb` 로
저장하고, 이 모델의 JSON Schema 가 OpenAPI 에 실려 sdk 타입이 함께 생성됩니다(P1-1).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


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


class McpServerBinding(BaseModel):
    """spec 0003 2.6, D-2: MCP Server 하나에 대한 바인딩 — `AgentDefinition` 의 필드로만
    존재합니다(새 테이블 없음). `ref` 는 배포가 소유합니다 — stdio 면 compose 가 아는
    서버 이름, http 면 내부 URL 키입니다. **자격증명이나 절대 URL 을 여기 넣지
    않습니다**(R-11) — 실제 값은 `AETHER_MCP_SERVERS`(spec 2.9)로 worker 가 풉니다.
    `name` 은 감사·정책 표의 `server_name` 과 같은 신분이고(spec 2.7 개정 4), 배포마다
    바뀌는 `ref` 와 달리 Agent 작성자가 고정합니다."""

    name: str
    transport: Literal["stdio", "http"]
    ref: str


class AgentDefinition(BaseModel):
    """`schema_version` 을 올리는 것은 파괴적 변경 판정 대상입니다(DP-1)."""

    schema_version: Literal[1]
    system_prompt: str
    model: ModelRef = Field(default_factory=ModelRef)
    tools: list[str] = Field(default_factory=list)
    policy: Policy = Field(default_factory=Policy)
    mcp_servers: list[McpServerBinding] = Field(default_factory=list)
    """spec 0003 2.6, D-2: 이 Agent Version 이 Run 시작 시 연결할 서버들(spec 2.5).
    기본값 빈 목록 — 바인딩이 비어 있으면 도구 없이 실행됩니다."""
    context_budget_tokens: int | None = Field(default=None, ge=1)
    """spec 0004 2.2, D-5: Context Compiler 가 쓰는 토큰 예산. `None` 이면
    `AETHER_CONTEXT_BUDGET_TOKENS`(기본 8192, worker 가 읽음)를 씁니다."""
    knowledge: list[str] = Field(default_factory=list)
    """spec 0004 2.2, D-5 (P3-3): 이 Agent Version 이 Run 시작 시 검색할 Knowledge
    Set **이름** 목록. 기본값 빈 목록 — 비어 있으면 검색하지 않습니다. 이름 →
    id 해석은 `aether_context` 의 어댑터가 합니다(이 패키지는 DB 를 모릅니다).
    바인딩 변경은 `mcp_servers`(spec 0003 D-2)와 같은 방식 — 새 HTTP 경로 없이
    기존 `PUT /agents/{id}` 가 새 Version 을 만듭니다(R-9)."""
    knowledge_top_k: int | None = Field(default=None, ge=1)
    """spec 0004 2.2, D-5 (P3-3): Knowledge 검색의 상위 k. `None` 이면
    `KnowledgeStore.DEFAULT_TOP_K`(5)를 씁니다."""

    @field_validator("system_prompt")
    @classmethod
    def _system_prompt_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("system_prompt must not be empty")
        return value

    @field_validator("tools")
    @classmethod
    def _tools_unique(cls, value: list[str]) -> list[str]:
        """spec 0003 2.15, D-16: 이름의 존재 여부는 더 이상 여기서 검증하지 않습니다
        — 도구는 Discovery 에서 오고, 없는 이름은 Run 시점에 `ToolNotFound` 로
        실패합니다. 중복만 여전히 여기서 막습니다(정의 자체의 결함)."""
        if len(value) != len(set(value)):
            raise ValueError("tools must not contain duplicates")
        return value

    @field_validator("knowledge")
    @classmethod
    def _knowledge_unique(cls, value: list[str]) -> list[str]:
        """spec 0004 D-5 (P3-3): `tools`(spec 0003 2.15, D-16)와 같은 방식 —
        존재 여부는 검증하지 않고(검색 시점에 해석, 미바인딩이면 조용히 미검색,
        R-9) 중복 이름만 막습니다(정의 자체의 결함)."""
        if len(value) != len(set(value)):
            raise ValueError("knowledge must not contain duplicates")
        return value
