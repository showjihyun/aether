"""spec 0004 2.4, D-4: `RedisKnowledgeIngestionStatusNotifier` — `KnowledgeIngestionStatusNotifier`
포트의 Redis Streams 구현(`RedisStatusNotifier` 와 같은 모양, spec 0002 2.18)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

import redis
from redis.typing import EncodableT, FieldT

from aether_worker.application.ports.outbound.knowledge_ingestion_status_notifier import (
    IngestionStatus,
)

_DEFAULT_STREAM = "aether:knowledge:ingestions:status"


class RedisKnowledgeIngestionStatusNotifier:
    def __init__(self, client: redis.Redis, *, stream: str = _DEFAULT_STREAM) -> None:
        self._client = client
        self._stream = stream

    def notify(
        self,
        ingestion_id: UUID,
        status: IngestionStatus,
        at: datetime,
        *,
        started_at: datetime | None = None,
        finished_at: datetime | None = None,
        failure_reason: str | None = None,
    ) -> None:
        fields: dict[FieldT, EncodableT] = {
            "ingestion_id": str(ingestion_id),
            "status": status,
            "at": at.isoformat(),
        }
        if started_at is not None:
            fields["started_at"] = started_at.isoformat()
        if finished_at is not None:
            fields["finished_at"] = finished_at.isoformat()
        if failure_reason is not None:
            fields["failure_reason"] = failure_reason
        self._client.xadd(self._stream, fields)
