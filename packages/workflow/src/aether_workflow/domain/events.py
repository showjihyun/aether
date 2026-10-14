"""spec 0005 2.10, D-13: Workflow 자기 이벤트 봉투와 payload. `v: 1`.

**왜 `aether_runtime.domain.events` 를 import 하지 않는가.** Workflow 는 자기 어휘
(`workflow.status`·`node.started`·`node.finished`·`workflow.finished`)를 가집니다. 이벤트
스키마는 계약이고(DP-1) 어휘가 다른 것을 한 계약에 섞으면 둘 다 바꾸기 어려워집니다 —
Agent Run 의 `EventType` 에 값을 더하면 Run 구독자가 모르는 타입을 만나고, 반대로 Workflow
구독자가 `task.started` 를 걸러야 합니다. 그리고 `aether_workflow` 가 `aether_runtime` 의
타입에 기대면 AR-13 의 반대 방향 결합이 생깁니다. 봉투의 **모양**(`v`·`seq`·`at`·`type`·
`payload`)만 같고 코드는 공유하지 않습니다. `approval.*` 는 P4-4 가 더합니다.

`seq` 는 Workflow Run 하나 안에서 1 부터 단조 증가하고, 상태 통지(`WorkflowStatusMessage`)가
같은 수열을 씁니다. 정본은 `data.workflow_run_executions.status_seq` 입니다.

`payload` 는 `dict[str, Any]` 로 두고 타입마다의 정확한 필드는 `*Payload` 모델이 소유합니다 —
`.model_dump(exclude_none=True)` 로 봉투에 실어 선택 필드가 없으면 키 자체가 빠집니다.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, get_args
from uuid import UUID

from pydantic import BaseModel, Field

WorkflowEventType = Literal[
    "workflow.status",
    "node.started",
    "node.finished",
    "workflow.finished",
]

WORKFLOW_EVENT_TYPES: frozenset[str] = frozenset(get_args(WorkflowEventType))


class WorkflowStatusPayload(BaseModel):
    """`workflow.status { status, current_node_id?, failure_reason? }` — 전이마다 하나."""

    status: str
    current_node_id: str | None = None
    failure_reason: str | None = None


class NodeStartedPayload(BaseModel):
    node_id: str
    kind: str
    iteration: int


class NodeFinishedPayload(BaseModel):
    node_id: str
    iteration: int
    status: str


class WorkflowFinishedPayload(BaseModel):
    """`workflow.finished { status }` — 항상 이벤트 스트림의 마지막."""

    status: str


PAYLOAD_MODELS: dict[str, type[BaseModel]] = {
    "workflow.status": WorkflowStatusPayload,
    "node.started": NodeStartedPayload,
    "node.finished": NodeFinishedPayload,
    "workflow.finished": WorkflowFinishedPayload,
}


class WorkflowEvent(BaseModel):
    """이벤트 봉투. `seq` 는 Workflow Run 안에서 1 부터 단조 증가합니다."""

    v: Literal[1] = 1
    workflow_run_id: UUID
    seq: int = Field(ge=1)
    at: datetime
    type: WorkflowEventType
    payload: dict[str, Any]
