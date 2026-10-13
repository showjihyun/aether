"""spec 0005 2.2, 2.9, D-12: Control Plane 의 Workflow 정의 쪽 예외와 값 객체.

노드·간선·`WorkflowVersion`·검증은 `aether_workflow.domain` 의 것을 그대로 씁니다 —
api 는 `aether_workflow.domain` 만 import 하고(`application`·`adapters` 는 import 하지
않습니다, `aether_runtime` 에 대한 AR-7 과 같은 경계) 그 타입을 복제하지 않습니다.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from aether_workflow.domain.workflow_version import WorkflowVersion


@dataclass(frozen=True)
class WorkflowView:
    """`control.workflows` 한 행과 그 최신 Version."""

    id: UUID
    name: str
    latest_version: WorkflowVersion


class WorkflowNotFound(Exception):
    """없는 Workflow."""

    def __init__(self, workflow_id: UUID) -> None:
        super().__init__(str(workflow_id))
        self.workflow_id = workflow_id
