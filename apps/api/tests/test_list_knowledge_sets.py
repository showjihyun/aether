"""spec 0006 2.3, D-3: `ListKnowledgeSetsUseCase` - 저장소의 커서 페이지를 그대로 전달합니다."""

from __future__ import annotations

from aether_api.application.usecases.list_knowledge_sets import ListKnowledgeSetsUseCase

from apps.api.tests.fakes_knowledge import FakeKnowledgeDeclarationStore


def test_list_knowledge_sets_pages_with_cursor() -> None:
    """spec 0006 2.3: limit 보다 많으면 next_cursor 로 나머지가 이어지고 마지막은 None."""
    store = FakeKnowledgeDeclarationStore()
    for name in ("a", "b", "c"):
        store.create_set(name)
    list_sets = ListKnowledgeSetsUseCase(store)

    page1 = list_sets(2, None)
    page2 = list_sets(2, page1.next_cursor)

    assert len(page1.items) == 2 and page1.next_cursor is not None
    assert len(page2.items) == 1 and page2.next_cursor is None
    assert {s.name for s in page1.items + page2.items} == {"a", "b", "c"}
