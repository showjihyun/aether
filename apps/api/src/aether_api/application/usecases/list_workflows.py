"""spec 0006 2.3, D-3: `ListWorkflows` 포트의 구현."""

from __future__ import annotations

from aether_api.application.ports.outbound.workflow_repository import WorkflowRepository
from aether_api.domain.workflow import WorkflowPage


class ListWorkflowsUseCase:
    """`WorkflowRepository` 하나로 inbound 포트 `ListWorkflows` 를 구현합니다."""

    def __init__(self, repository: WorkflowRepository) -> None:
        self._repository = repository

    def __call__(self, limit: int, cursor: str | None) -> WorkflowPage:
        return self._repository.list(limit, cursor)
