"""spec 0005 2.2, D-12: `GetWorkflowVersion` 포트의 구현."""

from __future__ import annotations

from uuid import UUID

from aether_workflow.domain.workflow_version import WorkflowVersion

from aether_api.application.ports.outbound.workflow_repository import WorkflowRepository


class GetWorkflowVersionUseCase:
    """`WorkflowRepository` 하나로 inbound 포트 `GetWorkflowVersion` 을 구현합니다."""

    def __init__(self, repository: WorkflowRepository) -> None:
        self._repository = repository

    def __call__(self, workflow_id: UUID, number: int) -> WorkflowVersion | None:
        return self._repository.get_version(workflow_id, number)
