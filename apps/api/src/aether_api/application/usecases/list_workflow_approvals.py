"""spec 0005 2.6, R-12 (P4-4): `ListWorkflowApprovals` 포트의 구현 - 승인 기록을 읽기만 합니다.

`domain`·`application.ports` 만 import 합니다(AR-9).
"""

from __future__ import annotations

from uuid import UUID

from aether_api.application.ports.outbound.workflow_approval_store import WorkflowApprovalStore
from aether_api.application.ports.outbound.workflow_run_declaration_store import (
    WorkflowRunDeclarationStore,
)
from aether_api.domain.workflow_approval import WorkflowApprovalView
from aether_api.domain.workflow_run import WorkflowRunNotFound


class ListWorkflowApprovalsUseCase:
    def __init__(self, runs: WorkflowRunDeclarationStore, approvals: WorkflowApprovalStore) -> None:
        self._runs = runs
        self._approvals = approvals

    def __call__(self, workflow_run_id: UUID) -> tuple[WorkflowApprovalView, ...]:
        if self._runs.get(workflow_run_id) is None:
            raise WorkflowRunNotFound(workflow_run_id)
        return self._approvals.list_for(workflow_run_id)
