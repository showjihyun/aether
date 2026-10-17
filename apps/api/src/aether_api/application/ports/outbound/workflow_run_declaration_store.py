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

from aether_api.domain.workflow_run import WorkflowRunPage, WorkflowRunView


class WorkflowRunDeclarationStore(Protocol):
    def create(
        self,
        workflow_id: UUID,
        workflow_version: int,
        input: dict[str, Any] | None,
        requested_by: UUID,
    ) -> WorkflowRunView:
        """`status = queued`, `status_seq = 0` 로 새 선언 행을 만듭니다. `requested_by` 는 요청한
        주체이고 자식 Agent Run 이 물려받습니다(`WorkflowRunView` 에는 싣지 않습니다). 커밋까지 이
        호출 안에서
        끝납니다. `(workflow_id, workflow_version)` 의 Version 행이 없으면
        `WorkflowVersionNotFound`."""
        ...

    def get(self, workflow_run_id: UUID) -> WorkflowRunView | None:
        """없으면 `None` — 유스케이스가 `WorkflowRunNotFound` 로 바꿉니다."""
        ...

    def list(
        self, limit: int, cursor: str | None, status: WorkflowRunStatus | None = None
    ) -> WorkflowRunPage:
        """`cursor` 이후 최대 `limit` 개를 `(requested_at, id)` 내림차순 - 최신 먼저(spec 0006 D-3).

        `control.workflow_runs` 투영만 읽습니다(`data` 평면은 모릅니다, spec 0006 D-4).
        `status` 가 주어지면 그 상태만. `next_cursor` 는 불투명 문자열.
        """
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
        waiting_node_execution_id: UUID | None = None,
        wake_at: datetime | None = None,
    ) -> bool:
        """`seq` 가 저장된 `status_seq` 보다 클 때만 한 UPDATE 로 적용합니다.

        `current_node_id`·`waiting_run_id`·`started_at`·`finished_at`·`failure_reason` 이
        `None` 이면 기존 값을 그대로 둡니다(`COALESCE(new, old)`). 적용됐으면 `True`,
        아니면(낮거나 같은 `seq`, 또는 없는 id) `False`.

        `waiting_run_id`·`waiting_node_execution_id` 는 예외입니다: **상태에서 유도**합니다 - 각각
        `waiting_run`·`waiting_approval` 일 때만 값이 있고(주지 않으면 이전 값) 다른 상태로 가면
        지워집니다. `wake_at`(P4-3)도 같은 규칙이고 `waiting_timer` 일 때만 값이 있습니다.
        """
        ...
