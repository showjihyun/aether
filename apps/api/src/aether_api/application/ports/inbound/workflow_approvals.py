"""spec 0005 2.6 개정 5, R-12 (P4-4): 승인 유스케이스 인터페이스.

HTTP 어댑터(`adapters/inbound/http/workflow_approvals.py`)는 이 포트 타입만 보고 부릅니다(AR-12).
"""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from aether_api.domain.workflow_approval import WorkflowApprovalView


class ApproveWorkflowNode(Protocol):
    """지목한 노드 실행을 승인합니다 - `approved_by` 는 인증된 주체의 id 이고 **판정하지 않고
    기록**합니다.

    던지는 예외(전부 정확성 가드이고 권한 판정이 아닙니다): `WorkflowRunNotFound`,
    `WorkflowRunNotWaitingApproval`, `NodeExecutionNotWaiting`, `AlreadyApproved`. 기록 뒤에
    `aether:workflow_runs:requested` 로 재큐하고, 재큐 실패는 승인을 막지 않습니다."""

    def __call__(
        self, workflow_run_id: UUID, node_execution_id: UUID, approved_by: str, note: str | None
    ) -> WorkflowApprovalView: ...


class ListWorkflowApprovals(Protocol):
    """Workflow Run 의 승인 기록. 없는 Run 이면 `WorkflowRunNotFound`."""

    def __call__(self, workflow_run_id: UUID) -> tuple[WorkflowApprovalView, ...]: ...
