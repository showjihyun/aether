"""spec 0005 2.3, 2.9 개정 2: `control.workflow_runs` 에 대한 outbound 포트.

fake(`apps/api/tests/fakes_workflow.py`)와 PostgreSQL 구현
(`adapters/outbound/db/workflow_run_declaration_store.py`)은 같은 계약을 만족해야 합니다.
Control Plane 은 **선언과 투영만** 합니다 — 실행 상태·lease(`data.workflow_run_executions`)는
모릅니다.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Protocol
from uuid import UUID

from aether_workflow.domain.run_status import WorkflowRunStatus

from aether_api.domain.workflow_run import WorkflowRunView


class WorkflowRunDeclarationStore(Protocol):
    def create(
        self, workflow_id: UUID, workflow_version: int, input: dict[str, Any] | None
    ) -> WorkflowRunView:
        """`status = queued`, `status_seq = 0` 로 새 선언 행을 만듭니다. 커밋까지 이 호출 안에서
        끝납니다. `(workflow_id, workflow_version)` 의 Version 행이 없으면
        `WorkflowVersionNotFound`."""
        ...

    def get(self, workflow_run_id: UUID) -> WorkflowRunView | None:
        """없으면 `None` — 유스케이스가 `WorkflowRunNotFound` 로 바꿉니다."""
        ...

    def apply_status(
        self,
        workflow_run_id: UUID,
        *,
        seq: int,
        status: WorkflowRunStatus,
        current_node_id: str | None,
        waiting_run_id: UUID | None,
        started_at: datetime | None,
        finished_at: datetime | None,
        failure_reason: str | None,
    ) -> bool:
        """`seq` 가 저장된 `status_seq` 보다 클 때만 한 UPDATE 로 적용합니다.

        `current_node_id`·`waiting_run_id`·`started_at`·`finished_at`·`failure_reason` 이
        `None` 이면 기존 값을 그대로 둡니다(`COALESCE(new, old)`). 적용됐으면 `True`,
        아니면(낮거나 같은 `seq`, 또는 없는 id) `False`.
        """
        ...
