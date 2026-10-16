"""spec 0005 2.6 개정 5, 2.9 (P4-4): `control.workflow_approvals` 에 대한 outbound 포트.

**쓰는 쪽은 api 뿐입니다** (실행기는 같은 표를 SELECT 로 읽기만 합니다 - 마이그레이션 0008).
append-only 이므로 이 포트에는 `record` 와 읽기만 있고 수정·삭제가 없습니다(트리거도 막습니다).
fake(`apps/api/tests/fakes_workflow.py`)와 PostgreSQL 구현은 같은 계약을 만족해야 합니다.
"""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from aether_api.domain.workflow_approval import WorkflowApprovalView


class WorkflowApprovalStore(Protocol):
    def record(
        self, workflow_run_id: UUID, node_execution_id: UUID, approved_by: str, note: str | None
    ) -> WorkflowApprovalView:
        """승인 한 건을 기록합니다. 같은 `(workflow_run_id, node_execution_id)` 가 이미 있으면
        `AlreadyApproved` - DB 의 unique 제약이 판정합니다(동시 요청에도 기록은 1건)."""
        ...

    def get(self, workflow_run_id: UUID, node_execution_id: UUID) -> WorkflowApprovalView | None:
        """그 노드 실행의 승인. 없으면 `None`."""
        ...

    def list_for(self, workflow_run_id: UUID) -> tuple[WorkflowApprovalView, ...]:
        """그 Run 의 승인 기록, 승인한 시각 순서."""
        ...
