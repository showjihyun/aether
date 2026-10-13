"""spec 0005 2.9, D-12: `WorkflowRepository` 포트의 인메모리 fake — 컨테이너 없이 Workflow
정의 유스케이스와 라우터를 돕니다(`fakes_knowledge.py` 와 같은 패턴). 테스트 지원 코드이며
제품 코드가 아닙니다.
"""

from __future__ import annotations

from uuid import UUID, uuid4

from aether_api.domain.workflow import WorkflowNotFound, WorkflowView
from aether_workflow.domain.node import Edge, Node
from aether_workflow.domain.workflow_version import WorkflowVersion


class FakeWorkflowRepository:
    """`WorkflowRepository` 포트 계약의 인메모리 구현."""

    def __init__(self) -> None:
        self._names: dict[UUID, str] = {}
        self._versions: dict[UUID, list[WorkflowVersion]] = {}

    def create(self, name: str, nodes: tuple[Node, ...], edges: tuple[Edge, ...]) -> WorkflowView:
        workflow_id = uuid4()
        version = WorkflowVersion(number=1, nodes=nodes, edges=edges)
        self._names[workflow_id] = name
        self._versions[workflow_id] = [version]
        return WorkflowView(id=workflow_id, name=name, latest_version=version)

    def add_version(
        self, workflow_id: UUID, nodes: tuple[Node, ...], edges: tuple[Edge, ...]
    ) -> WorkflowView:
        if workflow_id not in self._versions:
            raise WorkflowNotFound(workflow_id)
        version = WorkflowVersion(
            number=len(self._versions[workflow_id]) + 1, nodes=nodes, edges=edges
        )
        self._versions[workflow_id].append(version)
        return WorkflowView(id=workflow_id, name=self._names[workflow_id], latest_version=version)

    def get(self, workflow_id: UUID) -> WorkflowView | None:
        versions = self._versions.get(workflow_id)
        if versions is None:
            return None
        return WorkflowView(
            id=workflow_id, name=self._names[workflow_id], latest_version=versions[-1]
        )

    def get_version(self, workflow_id: UUID, number: int) -> WorkflowVersion | None:
        versions = self._versions.get(workflow_id, [])
        for version in versions:
            if version.number == number:
                return version
        return None
