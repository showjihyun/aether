"""spec 0005 2.9, D-12: `control.workflows`·`control.workflow_versions` 에 대한 outbound 포트.

fake(`apps/api/tests/fakes_workflow.py`)와 PostgreSQL 구현
(`adapters/outbound/db/workflow_repository.py`)이 같은 계약을 만족해야 합니다.
검증은 저장소가 아니라 유스케이스의 일입니다 — 여기 들어오는 노드·간선은 이미 통과했습니다.
"""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from aether_workflow.domain.node import Edge, Node
from aether_workflow.domain.workflow_version import WorkflowVersion

from aether_api.domain.workflow import WorkflowPage, WorkflowView


class WorkflowRepository(Protocol):
    def create(self, name: str, nodes: tuple[Node, ...], edges: tuple[Edge, ...]) -> WorkflowView:
        """`workflows` 행과 Version 1 을 **한 트랜잭션에** 만듭니다."""
        ...

    def add_version(
        self, workflow_id: UUID, nodes: tuple[Node, ...], edges: tuple[Edge, ...]
    ) -> WorkflowView:
        """행을 `SELECT … FOR UPDATE` 로 잠근 뒤 `current_version + 1` 로 새 Version 을
        넣고 `current_version` 을 갱신합니다. 기존 Version 은 건드리지 않습니다.
        없으면 `WorkflowNotFound`."""
        ...

    def get(self, workflow_id: UUID) -> WorkflowView | None: ...

    def get_version(self, workflow_id: UUID, number: int) -> WorkflowVersion | None: ...

    def list(self, limit: int, cursor: str | None) -> WorkflowPage:
        """`cursor` 이후 최대 `limit` 개를 `(created_at, id)` 오름차순으로(spec 0006 D-3).

        노드·간선은 읽지 않습니다 - 이름과 현재 Version 번호만. `next_cursor` 는 불투명 문자열.
        """
        ...
