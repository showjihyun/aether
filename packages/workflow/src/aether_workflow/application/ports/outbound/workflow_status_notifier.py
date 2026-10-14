"""spec 0005 2.9 개정 2: `WorkflowStatusMessage`·`WorkflowStatusNotifier` —
`aether:workflow_runs:status` 로 가는 투영 통지. `seq` 는 대응하는 `workflow.status` 이벤트의
`seq` 와 같은 수열입니다.

api 쪽 `WorkflowRunStatusMessage` 와 필드가 같지만 서로 import 하지 않습니다 — 스트림 계약이
정본입니다. `waiting_run_id` 는 `waiting_run` 일 때만 있습니다(파킹, P4-2a B2).
"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol
from uuid import UUID

from pydantic import BaseModel

from aether_workflow.domain.failure import WorkflowFailureReason
from aether_workflow.domain.run_status import WorkflowRunStatus


class WorkflowStatusMessage(BaseModel):
    workflow_run_id: UUID
    seq: int
    status: WorkflowRunStatus
    at: datetime
    current_node_id: str | None = None
    waiting_run_id: UUID | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    failure_reason: WorkflowFailureReason | None = None


class WorkflowStatusNotifier(Protocol):
    def notify(self, message: WorkflowStatusMessage) -> None: ...
