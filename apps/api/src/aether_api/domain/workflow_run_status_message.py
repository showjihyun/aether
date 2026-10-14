"""spec 0005 2.9 개정 2, 2.10: `WorkflowRunStatusMessage` — `aether:workflow_runs:status` 로
들어오는 투영 통지의 api 쪽 값 객체.

`aether_workflow.application` 쪽 상태 통지와 필드가 같지만 그것을 import 하지 않습니다 —
`aether_workflow.application` 은 api 에 금지된 모듈입니다(`aether_workflow.domain` 만 허용,
`domain/run_status_message.py` 와 같은 선). 스트림 계약이 정본이고 worker 와 api 양쪽이
각자 구현하며 서로의 코드를 import 하지 않습니다.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from aether_workflow.domain.run_status import WorkflowRunStatus
from pydantic import BaseModel


class WorkflowRunStatusMessage(BaseModel):
    """`aether:workflow_runs:status` 필드 — `WorkflowRunStatusConsumer` 가 파싱한 값."""

    workflow_run_id: UUID
    seq: int
    status: WorkflowRunStatus
    at: datetime
    current_node_id: str | None = None
    waiting_run_id: UUID | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    failure_reason: str | None = None
