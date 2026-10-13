"""spec 0005 2.2, D-12, R-1, R-2: Workflow 정의 경로의 inbound 포트.

**정의 경로는 Control Plane 의 것이므로 포트가 여기 있습니다** — `runs`·`knowledge` 의
inbound 포트가 `aether_api` 에 있는 것과 같은 자리입니다. `packages/workflow` 에 같은
포트를 한 벌 더 두었다가 지웠습니다(2026-10-13): api 는 `aether_workflow.domain` 만
import 하므로 그 포트를 쓸 수 없고, 쓰이지 않는 사본은 갈라지기만 합니다. 실행 쪽
(P4-2a)의 inbound 포트는 그때 `aether_workflow` 에 생깁니다 — 그것은 worker 가 씁니다.
잘못된 그래프는 `InvalidWorkflowGraph`(`aether_workflow.domain.validation`)
로 거부되고(R-1), 정의를 바꾸면 새 Version 이 됩니다(R-2).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from aether_workflow.domain.node import Edge, Node
from aether_workflow.domain.workflow_version import WorkflowVersion

from aether_api.domain.workflow import WorkflowView


@dataclass(frozen=True)
class DefineWorkflowRequest:
    name: str
    nodes: tuple[Node, ...]
    edges: tuple[Edge, ...]


@dataclass(frozen=True)
class UpdateWorkflowRequest:
    workflow_id: UUID
    nodes: tuple[Node, ...]
    edges: tuple[Edge, ...]


class DefineWorkflow(Protocol):
    def __call__(self, request: DefineWorkflowRequest) -> WorkflowView:
        """검증 뒤 Version 1 로 저장합니다. 실패하면 `InvalidWorkflowGraph`."""
        ...


class UpdateWorkflow(Protocol):
    def __call__(self, request: UpdateWorkflowRequest) -> WorkflowView:
        """새 Version 을 만듭니다. 기존 Version 은 바뀌지 않습니다(D-12).

        없으면 `WorkflowNotFound`, 검증 실패면 `InvalidWorkflowGraph`."""
        ...


class GetWorkflow(Protocol):
    def __call__(self, workflow_id: UUID) -> WorkflowView | None: ...


class GetWorkflowVersion(Protocol):
    def __call__(self, workflow_id: UUID, number: int) -> WorkflowVersion | None: ...
