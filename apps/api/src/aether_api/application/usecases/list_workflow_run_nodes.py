"""spec 0007 2.3, R-5 (P5-2): `ListWorkflowRunNodes` 포트의 구현 - 투영만 읽습니다.

없는 Run 은 빈 목록이 아니라 404 의 근거입니다(`ListIngestionsUseCase` 와 같은 선).
"""

from __future__ import annotations

from uuid import UUID

from aether_api.application.ports.outbound.workflow_node_state_reader import (
    WorkflowNodeStateReader,
)
from aether_api.application.ports.outbound.workflow_run_declaration_store import (
    WorkflowRunDeclarationStore,
)
from aether_api.domain.workflow_node_state import WorkflowNodeStatePage
from aether_api.domain.workflow_run import WorkflowRunNotFound


class ListWorkflowRunNodesUseCase:
    def __init__(
        self,
        runs: WorkflowRunDeclarationStore,
        nodes: WorkflowNodeStateReader,
    ) -> None:
        self._runs = runs
        self._nodes = nodes

    def __call__(
        self, workflow_run_id: UUID, limit: int, cursor: str | None
    ) -> WorkflowNodeStatePage:
        if self._runs.get(workflow_run_id) is None:
            raise WorkflowRunNotFound(workflow_run_id)
        return self._nodes.list_for_run(workflow_run_id, limit, cursor)
