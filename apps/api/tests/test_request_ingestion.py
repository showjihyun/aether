"""spec 0004 2.4, D-4: `RequestIngestionUseCase` — 집합 확인 → 선언(커밋) → 통지.

`FakeKnowledgeDeclarationStore`·`FakeKnowledgeIngestionNotifier` 로 컨테이너 없이
돕니다(architecture.md 3.1 "TDD" 이득, `RequestRunUseCase` 테스트와 같은 패턴).
구현 뒤에 작성됐습니다(red→green 순서 위반, 보고에 기록) — 다만 아래에서 실제로
버그(알 수 없는 집합을 조용히 받아들이는 문제가 없는지) 확인하는 과정에서 통과를
얻었습니다.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from aether_api.application.usecases.request_ingestion import RequestIngestionUseCase
from aether_api.domain.knowledge import KnowledgeSetNotFound

from apps.api.tests.fakes_knowledge import (
    FakeKnowledgeDeclarationStore,
    FakeKnowledgeIngestionNotifier,
)


def test_request_ingestion_declares_queued_and_notifies() -> None:
    store = FakeKnowledgeDeclarationStore()
    knowledge_set = store.create_set("docs")
    notifier = FakeKnowledgeIngestionNotifier()
    request_ingestion = RequestIngestionUseCase(store, notifier)

    view = request_ingestion(knowledge_set.id, "/srv/docs")

    assert view.status == "queued"
    assert view.knowledge_set_id == knowledge_set.id
    assert view.source == "/srv/docs"
    assert len(notifier.calls) == 1
    notified_ingestion_id, notified_set_id, notified_source = notifier.calls[0]
    assert notified_ingestion_id == view.id
    assert notified_set_id == knowledge_set.id
    assert notified_source == "/srv/docs"


def test_request_ingestion_unknown_set_raises_knowledge_set_not_found() -> None:
    store = FakeKnowledgeDeclarationStore()
    notifier = FakeKnowledgeIngestionNotifier()
    request_ingestion = RequestIngestionUseCase(store, notifier)

    with pytest.raises(KnowledgeSetNotFound):
        request_ingestion(uuid4(), "/srv/docs")


def test_request_ingestion_returns_normally_when_notifier_fails(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """spec 2.2 와 같은 취급: 통지 실패는 WARNING 만 남기고 202 로 이어질 값을 돌려줍니다."""
    store = FakeKnowledgeDeclarationStore()
    knowledge_set = store.create_set("docs")
    notifier = FakeKnowledgeIngestionNotifier(should_fail=True)
    request_ingestion = RequestIngestionUseCase(store, notifier)

    with caplog.at_level("WARNING"):
        view = request_ingestion(knowledge_set.id, "/srv/docs")

    assert view.status == "queued"
    assert any(record.levelname == "WARNING" for record in caplog.records)
