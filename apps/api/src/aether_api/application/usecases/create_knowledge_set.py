"""spec 0004 2.4, 2.8: `CreateKnowledgeSet` 포트의 구현 — 저장소에 그대로 위임합니다."""

from __future__ import annotations

from aether_api.application.ports.outbound.knowledge_declaration_store import (
    KnowledgeDeclarationStore,
)
from aether_api.domain.knowledge import KnowledgeSetView


class CreateKnowledgeSetUseCase:
    def __init__(self, store: KnowledgeDeclarationStore) -> None:
        self._store = store

    def __call__(self, name: str) -> KnowledgeSetView:
        return self._store.create_set(name)
