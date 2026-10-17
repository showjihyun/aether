"""spec 0006 2.3, D-3, D-4: `ListWorkflowRuns` 포트의 구현 - 투영만 읽습니다."""

from __future__ import annotations

from aether_workflow.domain.run_status import WorkflowRunStatus

from aether_api.application.ports.outbound.workflow_run_declaration_store import (
    WorkflowRunDeclarationStore,
)
from aether_api.domain.workflow_run import WorkflowRunPage


class ListWorkflowRunsUseCase:
    """`WorkflowRunDeclarationStore` 하나로 inbound 포트 `ListWorkflowRuns` 를 구현합니다."""

    def __init__(self, store: WorkflowRunDeclarationStore) -> None:
        self._store = store

    def __call__(
        self, limit: int, cursor: str | None, status: WorkflowRunStatus | None
    ) -> WorkflowRunPage:
        return self._store.list(limit, cursor, status)
