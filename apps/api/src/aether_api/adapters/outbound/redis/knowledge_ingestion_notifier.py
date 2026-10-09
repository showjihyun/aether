"""spec 0004 2.4, D-4: `RedisKnowledgeIngestionNotifier` — `KnowledgeIngestionNotifier`
포트의 Redis Streams 구현(`RedisRunNotifier` 와 같은 모양, spec 0002 2.18)."""

from __future__ import annotations

from uuid import UUID

import redis

_DEFAULT_STREAM = "aether:knowledge:ingestions:requested"


class RedisKnowledgeIngestionNotifier:
    def __init__(self, client: redis.Redis, *, stream: str = _DEFAULT_STREAM) -> None:
        self._client = client
        self._stream = stream

    def requested(self, ingestion_id: UUID, knowledge_set_id: UUID, source: str) -> None:
        self._client.xadd(
            self._stream,
            {
                "ingestion_id": str(ingestion_id),
                "knowledge_set_id": str(knowledge_set_id),
                "source": source,
            },
        )
