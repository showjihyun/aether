"""spec 0007 2.3, R-5, D-3 (P5-2): `ListWorkflowRunNodesUseCase` - 없는 Run 은 WorkflowRunNotFound,
있으면(노드가 없어도) 투영의 페이지."""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from aether_api.application.usecases.list_workflow_run_nodes import ListWorkflowRunNodesUseCase
from aether_api.domain.cursor import InvalidCursor
from aether_api.domain.workflow_node_state import WorkflowNodeStateView
from aether_api.domain.workflow_run import WorkflowRunNotFound
from aether_workflow.domain.node import Edge, Node, NodeKind
from aether_workflow.domain.node_execution import NodeExecutionStatus

from apps.api.tests.fakes_workflow import (
    FakeWorkflowNodeStateStore,
    FakeWorkflowRepository,
    FakeWorkflowRunDeclarationStore,
)


def _view(node_id: str) -> WorkflowNodeStateView:
    return WorkflowNodeStateView(
        node_id=node_id,
        kind="agent",
        status=NodeExecutionStatus.RUNNING,
        started_at=None,
        finished_at=None,
        failure_reason=None,
    )


class _World:
    def __init__(self) -> None:
        self.workflows = FakeWorkflowRepository()
        self.runs = FakeWorkflowRunDeclarationStore(self.workflows)
        self.nodes = FakeWorkflowNodeStateStore()
        self.list_nodes = ListWorkflowRunNodesUseCase(self.runs, self.nodes)

    def add_run(self) -> UUID:
        wf = self.workflows.create(
            f"wf-{uuid4()}", (Node("s", NodeKind.START), Node("e", NodeKind.END)), (Edge("s", "e"),)
        )
        return self.runs.create(wf.id, 1, None, uuid4()).workflow_run_id


def test_unknown_run_raises_not_found() -> None:
    """R-5: 없는 Workflow Run 은 빈 목록이 아니라 WorkflowRunNotFound."""
    with pytest.raises(WorkflowRunNotFound):
        _World().list_nodes(uuid4(), 50, None)


def test_run_without_nodes_is_an_empty_page() -> None:
    """R-5: 노드가 아직 없는 Run 은 오류가 아니라 빈 페이지."""
    world = _World()

    page = world.list_nodes(world.add_run(), 50, None)

    assert page.items == [] and page.next_cursor is None


def test_pages_only_that_runs_nodes() -> None:
    """spec 0006 D-3 (페이지 규칙 재사용): 그 Run 의 노드만, 커서로 이어진다."""
    world = _World()
    run, other = world.add_run(), world.add_run()
    for node_id in ("c", "a", "b"):
        world.nodes.put(run, _view(node_id))
    world.nodes.put(other, _view("zzz"))

    page1 = world.list_nodes(run, 2, None)
    page2 = world.list_nodes(run, 2, page1.next_cursor)

    assert [n.node_id for n in page1.items] == ["a", "b"] and page1.next_cursor is not None
    assert [n.node_id for n in page2.items] == ["c"] and page2.next_cursor is None


def test_bad_cursor_propagates_invalid_cursor() -> None:
    """spec 0006 2.3: 깨진 커서는 InvalidCursor 로 올라간다(HTTP 가 422 로)."""
    world = _World()

    with pytest.raises(InvalidCursor):
        world.list_nodes(world.add_run(), 50, "!!")
