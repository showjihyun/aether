"""spec 0005 2.2: `GetWorkflow` 포트의 구현."""

from __future__ import annotations

from uuid import UUID

from aether_api.application.ports.outbound.workflow_repository import WorkflowRepository
from aether_api.domain.workflow import WorkflowView


class GetWorkflowUseCase:
    """`WorkflowRepository` 하나로 inbound 포트 `GetWorkflow` 를 구현합니다."""

    def __init__(self, repository: WorkflowRepository) -> None:
        self._repository = repository

    def __call__(self, workflow_id: UUID) -> WorkflowView | None:
        return self._repository.get(workflow_id)
