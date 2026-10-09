"""spec 0004 2.4: `GetIngestion` 포트의 구현 — `GetRunUseCase` 와 같은 모양."""

from __future__ import annotations

from uuid import UUID

from aether_api.application.ports.outbound.knowledge_declaration_store import (
    KnowledgeDeclarationStore,
)
from aether_api.domain.knowledge import KnowledgeIngestionNotFound, KnowledgeIngestionView


class GetIngestionUseCase:
    def __init__(self, store: KnowledgeDeclarationStore) -> None:
        self._store = store

    def __call__(self, ingestion_id: UUID) -> KnowledgeIngestionView:
        view = self._store.get_ingestion(ingestion_id)
        if view is None:
            raise KnowledgeIngestionNotFound(ingestion_id)
        return view
