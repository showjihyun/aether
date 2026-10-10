"""spec 0004 2.1, 2.2, 2.3, AR-3, AR-12, D-11, R-3: `ContextCompiler` — runtime 이
모델 입력을 조립하기 전에 지나는 **유일한** outbound 포트.

`aether_runtime.application` 이 바깥(`aether_context`)에 요구하는 계약입니다 —
`ToolGateway`(spec 0003 2.1)와 같은 자리입니다: 이 포트 자체는 `aether_context`
를 import 하지 않고 자신의 값 타입만 씁니다. runtime 은 `aether_context` 의
inbound 포트 타입만 보는 어댑터(`adapters/outbound/context_compiler/`)를 통해서만
이 포트를 구현합니다 — 조립은 worker 의 `main.py` 가 맡습니다(AR-10).
"""

from __future__ import annotations

from typing import Protocol

from pydantic import BaseModel, Field

from aether_runtime.application.ports.outbound.model_gateway import ToolSchema
from aether_runtime.domain.run import Message

DEFAULT_KNOWLEDGE_TOP_K = 5
"""spec 0004 D-5 (P3-3): `AgentDefinition.knowledge_top_k` 가 `None` 일 때의 상위 k.
`aether_runtime` 안에서는 이 상수가 유일한 출처입니다. `aether_context` 의
`knowledge_store.DEFAULT_TOP_K`·`compile_context._DEFAULT_KNOWLEDGE_TOP_K` 와 같은
숫자여야 하지만 AR-3 때문에 import 하지 않고 숫자만 맞춥니다(서로 주석으로 가리킴)."""


class ContextSourceTokens(BaseModel):
    """소스 하나의 (드롭 적용 전) 토큰 추정."""

    source: str
    tokens: int


class ContextDrop(BaseModel):
    """예산 초과로 뺀 소스 하나와 그 양(토큰)."""

    source: str
    tokens: int


class ContextReport(BaseModel):
    """spec 2.3, D-11: 조립 결과와 함께 돌아가는 보고. 본문을 넣지 않습니다 —
    숫자와 종류만입니다."""

    budget_tokens: int
    source_tokens: tuple[ContextSourceTokens, ...] = Field(default_factory=tuple)
    total_tokens: int = 0
    dropped: tuple[ContextDrop, ...] = Field(default_factory=tuple)


class CompiledContext(BaseModel):
    """`ContextCompiler.compile` 의 결과 — 모델에 그대로 보낼 `messages`·`tools`
    와 그 조립을 설명하는 `report`."""

    messages: tuple[Message, ...]
    tools: tuple[ToolSchema, ...] = Field(default_factory=tuple)
    report: ContextReport


class ContextCompiler(Protocol):
    """spec 2.1 도해의 `runtime -> context` 경계. `ExecuteRunUseCase` 는 모델을
    부르기 전에 이 포트만 지납니다(R-3) — 메시지를 직접 조립하지 않습니다."""

    def compile(
        self,
        *,
        system_prompt: str,
        conversation: tuple[Message, ...],
        tools: tuple[ToolSchema, ...],
        budget_tokens: int,
        knowledge_sets: tuple[str, ...] = (),
        knowledge_top_k: int = DEFAULT_KNOWLEDGE_TOP_K,
    ) -> CompiledContext:
        """`system_prompt`·`conversation`(지금까지의 메시지)·`tools` 를 `budget_tokens`
        안으로 결정적으로 조립합니다(R-1, R-2). `knowledge_sets`(spec 0004 D-5,
        P3-3)는 `AgentDefinition.knowledge` — 비어 있으면 검색하지 않습니다."""
        ...
