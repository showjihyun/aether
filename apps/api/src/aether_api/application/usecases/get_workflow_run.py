"""spec 0005 2.3, R-13: `GetWorkflowRun` 포트의 구현 — 투영만 읽습니다.

`domain`·`application.ports` 만 import 합니다(AR-9).
"""

from __future__ import annotations

from uuid import UUID

from aether_api.application.ports.outbound.workflow_run_declaration_store import (
    WorkflowRunDeclarationStore,
)
from aether_api.domain.workflow_run import WorkflowRunNotFound, WorkflowRunView


class GetWorkflowRunUseCase:
    """`WorkflowRunDeclarationStore` 하나로 inbound 포트 `GetWorkflowRun` 을 구현합니다."""

    def __init__(self, store: WorkflowRunDeclarationStore) -> None:
        self._store = store

    def __call__(self, workflow_run_id: UUID) -> WorkflowRunView:
        view = self._store.get(workflow_run_id)
        if view is None:
            raise WorkflowRunNotFound(workflow_run_id)
        return view
