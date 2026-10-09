"""spec 0004 2.4, D-4: `GetIngestionUseCase` — `GetRunUseCase` 와 같은 모양."""

from __future__ import annotations

from uuid import uuid4

import pytest
from aether_api.application.usecases.get_ingestion import GetIngestionUseCase
from aether_api.domain.knowledge import KnowledgeIngestionNotFound

from apps.api.tests.fakes_knowledge import FakeKnowledgeDeclarationStore


def test_get_ingestion_unknown_raises_not_found() -> None:
    store = FakeKnowledgeDeclarationStore()
    get_ingestion = GetIngestionUseCase(store)

    with pytest.raises(KnowledgeIngestionNotFound):
        get_ingestion(uuid4())


def test_get_ingestion_returns_declared_view() -> None:
    store = FakeKnowledgeDeclarationStore()
    knowledge_set = store.create_set("docs")
    ingestion = store.create_ingestion(knowledge_set.id, "/srv/docs")
    get_ingestion = GetIngestionUseCase(store)

    view = get_ingestion(ingestion.id)
    assert view.id == ingestion.id
    assert view.status == "queued"
