"""spec 0005 2.2, R-1: `DefineWorkflow` 포트의 구현.

검증은 **저장 시점**입니다 — `validate_version` 이 위반을 돌려주면 저장소를 부르지 않고
`InvalidWorkflowGraph` 를 던집니다. `aether_workflow.domain` 만 import 합니다.
"""

from __future__ import annotations

from aether_workflow.domain.validation import InvalidWorkflowGraph, validate_version
from aether_workflow.domain.workflow_version import WorkflowVersion

from aether_api.application.ports.inbound.workflows import DefineWorkflowRequest
from aether_api.application.ports.outbound.workflow_repository import WorkflowRepository
from aether_api.domain.workflow import WorkflowView


class DefineWorkflowUseCase:
    """`WorkflowRepository` 하나로 inbound 포트 `DefineWorkflow` 를 구현합니다."""

    def __init__(self, repository: WorkflowRepository) -> None:
        self._repository = repository

    def __call__(self, request: DefineWorkflowRequest) -> WorkflowView:
        # 번호는 저장소가 정합니다. 검증은 번호를 보지 않으므로 자리표시자 0 을 씁니다.
        violations = validate_version(
            WorkflowVersion(number=0, nodes=request.nodes, edges=request.edges)
        )
        if violations:
            raise InvalidWorkflowGraph(violations)
        return self._repository.create(request.name, request.nodes, request.edges)
