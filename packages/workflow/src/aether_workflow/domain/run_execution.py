"""spec 0005 2.9 개정 2: `data.workflow_run_executions` 한 행의 값 객체 — 실행 상태의 정본."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from aether_workflow.domain.run_status import WorkflowRunStatus


@dataclass(frozen=True)
class WorkflowRunExecution:
    workflow_run_id: UUID
    status: WorkflowRunStatus
    status_seq: int
    current_node_id: str | None
    started_at: datetime | None
    finished_at: datetime | None
    failure_reason: str | None
    waiting_run_id: UUID | None = None
    waiting_node_execution_id: UUID | None = None
    """`waiting_approval` 일 때만 값이 있다 - 승인이 지목해야 하는 노드 실행(R-12)."""
    wake_at: datetime | None = None
    """`waiting_timer` 일 때만 값이 있다 - `WAIT` 가 깨어날 시각(spec 0005 2.7 개정 7 (5))."""
