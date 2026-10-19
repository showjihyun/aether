"""spec 0002 2.7, D-4: Run 이벤트 봉투와 8종 payload. `v: 1`.

`RunEvent` 는 SSE `data` 봉투 그대로입니다(`{ v, run_id, seq, at, type, payload }`).
`payload` 는 `dict[str, Any]` 로 두고, 8종 각각의 정확한 필드는 아래 `*Payload`
pydantic 모델이 소유합니다 — 유스케이스는 이 모델로 값을 만들고
`.model_dump(exclude_none=True)` 로 봉투에 실어, `?` 로 표시된 선택 필드(예:
`run.status.failure_reason`)가 없을 때 키 자체가 빠지게 합니다.

`model.delta` 는 D-17(MVP-2d)부터 실제로 발생합니다 — 루프가 `stream` 을 쓰고 텍스트
조각마다 하나를 다른 이벤트와 똑같이 저장합니다. reasoning(D-19)은 내지 않습니다.

각 `*Payload` 는 `.model_json_schema()` 를 그대로 낼 수 있습니다 — `PAYLOAD_MODELS` 가
`aether-api events-schema`(P1-6)의 근거가 됩니다.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, get_args
from uuid import UUID

from pydantic import BaseModel, Field

EventType = Literal[
    "run.status",
    "task.started",
    "task.finished",
    "model.completed",
    "tool.called",
    "tool.result",
    "run.finished",
    "model.delta",
]

EVENT_TYPES: frozenset[str] = frozenset(get_args(EventType))


class RunStatusPayload(BaseModel):
    """`run.status { status, failure_reason? }` — 2.4 의 전이마다 하나."""

    status: str
    failure_reason: str | None = None


class TaskStartedPayload(BaseModel):
    task_id: str
    step: int


class TaskFinishedPayload(BaseModel):
    task_id: str


class ModelCompletedPayload(BaseModel):
    finish_reason: str
    usage: dict[str, int] | None = None


class ToolCalledPayload(BaseModel):
    task_id: str
    tool_call_id: str
    name: str
    arguments: dict[str, Any]


class ToolResultPayload(BaseModel):
    task_id: str
    tool_call_id: str
    name: str
    is_error: bool
    content: str
    truncated: bool


class RunFinishedPayload(BaseModel):
    """`run.finished { status }` — 항상 이벤트 스트림의 마지막."""

    status: str


class ModelDeltaPayload(BaseModel):
    """`model.delta { text }` — 모델 답변의 조각 하나. 도착하는 대로 하나씩 발행되고
    다른 이벤트와 똑같이 저장됩니다(D-17). 이으면 그 턴의 답변 전체입니다."""

    text: str


PAYLOAD_MODELS: dict[str, type[BaseModel]] = {
    "run.status": RunStatusPayload,
    "task.started": TaskStartedPayload,
    "task.finished": TaskFinishedPayload,
    "model.completed": ModelCompletedPayload,
    "tool.called": ToolCalledPayload,
    "tool.result": ToolResultPayload,
    "run.finished": RunFinishedPayload,
    "model.delta": ModelDeltaPayload,
}


class RunEvent(BaseModel):
    """SSE `data` 봉투(2.7). `seq` 는 Run 안에서 1 부터 단조 증가합니다."""

    v: Literal[1] = 1
    run_id: UUID
    seq: int = Field(ge=1)
    at: datetime
    type: EventType
    payload: dict[str, Any]
