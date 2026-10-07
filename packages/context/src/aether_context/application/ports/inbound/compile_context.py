"""spec 0004 2.1, 2.2, 2.3, D-11, D-12, R-1, R-2: `CompileContext` inbound 포트 —
Context Compiler 유스케이스의 계약.

`aether_runtime` 은 이 모듈(과 `domain` 의 값 타입)만 봅니다(AR-12) — 구현
(`application/usecases/compile_context.py`)과 `adapters` 는 보지 않습니다.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from aether_context.domain.message import ContextMessage
from aether_context.domain.report import ContextReport
from aether_context.domain.tool_schema import ContextToolSchema


@dataclass(frozen=True)
class CompileContextRequest:
    """조립할 소스 전부와 예산. `conversation`·`tools` 는 호출자가 건넨 **순서
    그대로** 쓰입니다 — 결정성(R-1, D-12)을 위해 이 안에서 재정렬하지 않습니다."""

    system_prompt: str
    budget_tokens: int
    conversation: tuple[ContextMessage, ...] = field(default_factory=tuple)
    tools: tuple[ContextToolSchema, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class CompileContextResult:
    """조립된 모델 입력(`messages`·`tools`)과 `ContextReport`(D-11)."""

    messages: tuple[ContextMessage, ...]
    tools: tuple[ContextToolSchema, ...]
    report: ContextReport


class CompileContext(Protocol):
    def __call__(self, request: CompileContextRequest) -> CompileContextResult:
        """`request` 의 소스를 예산 안으로 결정적으로 조립합니다(R-1, R-2)."""
        ...
