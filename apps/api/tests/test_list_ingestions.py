"""spec 0006 2.3, D-3: `ListIngestionsUseCase` - 없는 집합은 KnowledgeSetNotFound, 있으면 페이지."""

from __future__ import annotations

from uuid import uuid4

import pytest
from aether_api.application.usecases.list_ingestions import ListIngestionsUseCase
from aether_api.domain.knowledge import KnowledgeSetNotFound

from apps.api.tests.fakes_knowledge import FakeKnowledgeDeclarationStore


def test_list_ingestions_raises_for_unknown_set() -> None:
    """spec 0006 2.3: 없는 집합이면 빈 목록이 아니라 KnowledgeSetNotFound."""
    with pytest.raises(KnowledgeSetNotFound):
        ListIngestionsUseCase(FakeKnowledgeDeclarationStore())(uuid4(), 50, None, None)


def test_list_ingestions_pages_and_filters_by_status() -> None:
    """spec 0006 2.3: 그 집합의 적재만, 상태 필터와 커서가 이어진다."""
    store = FakeKnowledgeDeclarationStore()
    knowledge_set = store.create_set("s")
    for _ in range(3):
        store.create_ingestion(knowledge_set.id, "/d")
    done = store.create_ingestion(knowledge_set.id, "/d")
    store.apply_ingestion_status(
        done.id, status="succeeded", started_at=None, finished_at=None, failure_reason=None
    )
    list_ingestions = ListIngestionsUseCase(store)

    page1 = list_ingestions(knowledge_set.id, 3, None, None)
    page2 = list_ingestions(knowledge_set.id, 3, page1.next_cursor, None)
    only_done = list_ingestions(knowledge_set.id, 50, None, "succeeded")

    assert len(page1.items) == 3 and page1.next_cursor is not None
    assert len(page2.items) == 1 and page2.next_cursor is None
    assert [i.id for i in only_done.items] == [done.id]
