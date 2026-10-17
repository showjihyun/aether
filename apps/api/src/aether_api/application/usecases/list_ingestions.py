"""spec 0006 2.3, D-3: `ListIngestions` 포트의 구현 - 없는 집합은 빈 목록이 아니라 404 의 근거."""

from __future__ import annotations

from uuid import UUID

from aether_api.application.ports.outbound.knowledge_declaration_store import (
    KnowledgeDeclarationStore,
)
from aether_api.domain.knowledge import (
    IngestionStatus,
    KnowledgeIngestionPage,
    KnowledgeSetNotFound,
)


class ListIngestionsUseCase:
    """`KnowledgeDeclarationStore` 하나로 inbound 포트 `ListIngestions` 를 구현합니다."""

    def __init__(self, store: KnowledgeDeclarationStore) -> None:
        self._store = store

    def __call__(
        self,
        knowledge_set_id: UUID,
        limit: int,
        cursor: str | None,
        status: IngestionStatus | None,
    ) -> KnowledgeIngestionPage:
        if self._store.get_set(knowledge_set_id) is None:
            raise KnowledgeSetNotFound(knowledge_set_id)
        return self._store.list_ingestions(knowledge_set_id, limit, cursor, status)
