"""spec 0005 2.9 개정 2: `WorkflowRunStateStore` — `data.workflow_run_executions`(상태·lease)와
`data.workflow_node_executions`(노드 실행 기록) 계약.

시각은 전부 **DB 시계**(`now()`) 기준입니다 — lease 만료는 저장소가 소유한 시계 하나로
여러 worker 사이의 경합을 판정합니다(`RunStateStore` 와 같은 선).
"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol
from uuid import UUID

from aether_workflow.domain.failure import WorkflowFailureReason
from aether_workflow.domain.node_execution import NodeExecutionRecord, NodeExecutionStatus
from aether_workflow.domain.run_execution import WorkflowRunExecution
from aether_workflow.domain.run_status import WorkflowRunStatus


class WorkflowRunStateStore(Protocol):
    def acquire_lease(self, workflow_run_id: UUID, owner: str, ttl_seconds: float) -> bool:
        """행이 없으면 `queued` 실행 행을 만들고 잡습니다. `lease_until` 이 비었거나
        지났을 때만 성공합니다(조건부 UPDATE 한 문장, 원자적)."""
        ...

    def renew_lease(self, workflow_run_id: UUID, owner: str, ttl_seconds: float) -> bool: ...

    def release(self, workflow_run_id: UUID, owner: str) -> None:
        """`owner` 가 쥔 lease 만 놓습니다."""
        ...

    def load(self, workflow_run_id: UUID) -> WorkflowRunExecution | None: ...

    def set_status(
        self,
        workflow_run_id: UUID,
        status: WorkflowRunStatus,
        *,
        seq: int,
        current_node_id: str | None = None,
        failure_reason: WorkflowFailureReason | None = None,
        started_at: datetime | None = None,
        finished_at: datetime | None = None,
    ) -> None:
        """`current_node_id`·`failure_reason`·`started_at`·`finished_at` 은 주었을 때만
        채웁니다(COALESCE) — 주지 않은 호출이 이전 값을 지우지 않습니다. `seq` 는 항상 씁니다."""
        ...

    def start_node(self, workflow_run_id: UUID, node_id: str, iteration: int) -> UUID | None:
        """`INSERT … ON CONFLICT DO NOTHING RETURNING id`. **`None` 은 "이미 기록돼 있다"** —
        그것이 멱등·재개의 축입니다(R-6, R-8)."""
        ...

    def finish_node(
        self, node_execution_id: UUID, status: NodeExecutionStatus, finished_at: datetime
    ) -> None: ...

    def node_executions(self, workflow_run_id: UUID) -> tuple[NodeExecutionRecord, ...]: ...
