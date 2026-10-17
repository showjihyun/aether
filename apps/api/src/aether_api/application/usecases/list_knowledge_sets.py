"""spec 0006 2.3, D-3: `ListKnowledgeSets` 포트의 구현."""

from __future__ import annotations

from aether_api.application.ports.outbound.knowledge_declaration_store import (
    KnowledgeDeclarationStore,
)
from aether_api.domain.knowledge import KnowledgeSetPage


class ListKnowledgeSetsUseCase:
    """`KnowledgeDeclarationStore` 하나로 inbound 포트 `ListKnowledgeSets` 를 구현합니다."""

    def __init__(self, store: KnowledgeDeclarationStore) -> None:
        self._store = store

    def __call__(self, limit: int, cursor: str | None) -> KnowledgeSetPage:
        return self._store.list_sets(limit, cursor)
