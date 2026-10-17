"""spec 0006 2.3, D-3: `ListWorkflowsUseCase` - 저장소의 커서 페이지를 그대로 전달합니다."""

from __future__ import annotations

from aether_api.application.usecases.list_workflows import ListWorkflowsUseCase
from aether_workflow.domain.node import Edge, Node, NodeKind

from apps.api.tests.fakes_workflow import FakeWorkflowRepository


def test_list_workflows_pages_with_cursor() -> None:
    """spec 0006 2.3: limit 보다 많으면 next_cursor 로 나머지가 이어지고 마지막은 None."""
    repo = FakeWorkflowRepository()
    for name in ("a", "b", "c"):
        repo.create(name, (Node("s", NodeKind.START), Node("e", NodeKind.END)), (Edge("s", "e"),))
    list_workflows = ListWorkflowsUseCase(repo)

    page1 = list_workflows(2, None)
    page2 = list_workflows(2, page1.next_cursor)

    assert len(page1.items) == 2 and page1.next_cursor is not None
    assert len(page2.items) == 1 and page2.next_cursor is None
    assert {w.name for w in page1.items + page2.items} == {"a", "b", "c"}
