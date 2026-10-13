"""spec 0005 2.2, R-1, R-2, D-12: `UpdateWorkflow` 포트의 구현 — 새 Version 을 만듭니다.

기존 Version 은 바뀌지 않습니다. 검증은 저장 시점이고 실패하면 새 Version 이 생기지
않습니다. `aether_workflow.domain` 만 import 합니다.
"""

from __future__ import annotations

from aether_workflow.domain.validation import InvalidWorkflowGraph, validate_version
from aether_workflow.domain.workflow_version import WorkflowVersion

from aether_api.application.ports.inbound.workflows import UpdateWorkflowRequest
from aether_api.application.ports.outbound.workflow_repository import WorkflowRepository
from aether_api.domain.workflow import WorkflowView


class UpdateWorkflowUseCase:
    """`WorkflowRepository` 하나로 inbound 포트 `UpdateWorkflow` 를 구현합니다."""

    def __init__(self, repository: WorkflowRepository) -> None:
        self._repository = repository

    def __call__(self, request: UpdateWorkflowRequest) -> WorkflowView:
        violations = validate_version(
            WorkflowVersion(number=0, nodes=request.nodes, edges=request.edges)
        )
        if violations:
            raise InvalidWorkflowGraph(violations)
        return self._repository.add_version(request.workflow_id, request.nodes, request.edges)
