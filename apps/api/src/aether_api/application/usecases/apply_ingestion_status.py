"""spec 0004 2.4, D-4: `ApplyIngestionStatus` 포트의 구현 — 저장소에 그대로 위임."""

from __future__ import annotations

from aether_api.application.ports.outbound.knowledge_declaration_store import (
    KnowledgeDeclarationStore,
)
from aether_api.domain.knowledge_ingestion_status_message import KnowledgeIngestionStatusMessage


class ApplyIngestionStatusUseCase:
    def __init__(self, store: KnowledgeDeclarationStore) -> None:
        self._store = store

    def __call__(self, message: KnowledgeIngestionStatusMessage) -> bool:
        return self._store.apply_ingestion_status(
            message.ingestion_id,
            status=message.status,
            started_at=message.started_at,
            finished_at=message.finished_at,
            failure_reason=message.failure_reason,
        )
