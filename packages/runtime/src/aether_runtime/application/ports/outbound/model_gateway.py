"""spec 0002 2.5, D-19, R-6 (P1-3): `ModelGateway` — model-agnostic 인터페이스.

`domain.run.Message`(`role`, `content`, `tool_call_id`)와 `domain.tools.ToolCall`을
그대로 재사용합니다(AR-9 — pydantic 은 검증 라이브러리이지 I/O 가 아니므로 여기서도
막지 않습니다). 어댑터는 `adapters/outbound/model_gateway/` 안에만 있고, 그 밖 어디도
LLM SDK/HTTP 를 부르지 않습니다(backlog P1-3 완료 판정, AR-5).

`reasoning`(D-19)은 로그·span·이벤트에 넣지 않습니다 — 이 모듈은 그 값을 로그로
남기지 않습니다(로그 자체가 없습니다).
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any, Literal, Protocol

from pydantic import BaseModel, Field

from aether_runtime.domain.run import Message
from aether_runtime.domain.tools import ToolCall


class ToolSchema(BaseModel):
    """모델에 알려줄 도구 하나의 스키마 — MCP tool 과 같은 모양(D-5)."""

    name: str
    description: str
    input_schema: dict[str, Any]


class ModelRequest(BaseModel):
    """`ModelGateway.complete`/`stream` 에 건네는 요청.

    `model_id` 가 `None` 이면 어댑터가 배포 설정(`AETHER_MODEL_ID`)의 기본값을 씁니다.
    """

    messages: list[Message]
    tools: list[ToolSchema] = Field(default_factory=list)
    model_id: str | None = None


class ModelResponse(BaseModel):
    """`complete` 의 응답. `reasoning` 은 thinking 모델의 사고 과정(D-19) — `text` 와
    분리되어 있습니다."""

    text: str = ""
    tool_calls: list[ToolCall] = Field(default_factory=list)
    reasoning: str | None = None
    finish_reason: str
    usage: dict[str, int] | None = None


class ModelDelta(BaseModel):
    """`stream` 이 내는 조각 하나. `done=True` 는 스트림의 마지막 조각입니다."""

    text: str | None = None
    tool_call: ToolCall | None = None
    reasoning: str | None = None
    done: bool = False


class ModelError(Exception):
    """모델 호출 실패 — `kind` 로 재시도 정책(P1-7)이 분기합니다."""

    def __init__(
        self,
        kind: Literal["http", "timeout", "protocol"],
        *,
        status: int | None = None,
        message: str | None = None,
    ) -> None:
        super().__init__(message or f"model gateway error: kind={kind} status={status}")
        self.kind = kind
        self.status = status


class ModelGateway(Protocol):
    """model-agnostic 게이트웨이(spec 0002 2.5, AR-5, DP-3). 어댑터는
    `adapters/outbound/model_gateway/` 안에만 둡니다."""

    def complete(self, request: ModelRequest) -> ModelResponse: ...

    def stream(self, request: ModelRequest) -> Iterator[ModelDelta]: ...

    def embed(self, texts: list[str]) -> list[list[float]]: ...
