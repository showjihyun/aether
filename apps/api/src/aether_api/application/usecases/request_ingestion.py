"""spec 0004 2.4, D-4: `RequestIngestion` 포트의 구현 — 선언(커밋) → 통지.

`RequestRunUseCase`(spec 0002)와 같은 모양입니다 — `KnowledgeDeclarationStore.
create_ingestion` 이 커밋까지 끝낸 뒤, `KnowledgeIngestionNotifier.requested` 가
실패해도(예: Redis 장애) `202` 를 막지 않습니다 — WARNING 만 남기고 그대로
`KnowledgeIngestionView` 를 반환합니다(적재는 `queued` 로 남아 관측 가능).
"""

from __future__ import annotations

import logging
from uuid import UUID

from aether_api.application.ports.outbound.knowledge_declaration_store import (
    KnowledgeDeclarationStore,
)
from aether_api.application.ports.outbound.knowledge_ingestion_notifier import (
    KnowledgeIngestionNotifier,
)
from aether_api.domain.knowledge import KnowledgeIngestionView, KnowledgeSetNotFound

logger = logging.getLogger(__name__)


class RequestIngestionUseCase:
    def __init__(
        self, store: KnowledgeDeclarationStore, notifier: KnowledgeIngestionNotifier
    ) -> None:
        self._store = store
        self._notifier = notifier

    def __call__(self, knowledge_set_id: UUID, source: str) -> KnowledgeIngestionView:
        if self._store.get_set(knowledge_set_id) is None:
            raise KnowledgeSetNotFound(knowledge_set_id)

        view = self._store.create_ingestion(knowledge_set_id, source)

        try:
            self._notifier.requested(view.id, knowledge_set_id, source)
        except Exception:  # noqa: BLE001 -- XADD 실패는 WARNING 만, 202 는 막지 않습니다
            logger.warning(
                "knowledge.ingestion.notify_failed",
                extra={"ingestion_id": str(view.id), "knowledge_set_id": str(knowledge_set_id)},
            )

        return view
