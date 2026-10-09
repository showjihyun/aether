"""spec 0004 2.4, 2.8: `CreateKnowledgeSetUseCase` — 저장소에 그대로 위임."""

from __future__ import annotations

from apps.api.tests.fakes_knowledge import FakeKnowledgeDeclarationStore


def test_create_knowledge_set_returns_declared_view() -> None:
    from aether_api.application.usecases.create_knowledge_set import CreateKnowledgeSetUseCase

    store = FakeKnowledgeDeclarationStore()
    create_knowledge_set = CreateKnowledgeSetUseCase(store)

    view = create_knowledge_set("docs")

    assert view.name == "docs"
    assert store.get_set(view.id) == view
