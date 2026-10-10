"""spec 0004 2.6, D-9, R-1 (P3-4): `ReadAgentMemoryUseCase` — `ReadAgentMemory` 의 구현."""

from __future__ import annotations

from uuid import UUID

from aether_memory.application.ports.outbound.embedder import Embedder
from aether_memory.application.ports.outbound.memory_store import MemoryStore
from aether_memory.domain.memory import MemoryHit


class ReadAgentMemoryUseCase:
    def __init__(self, embedder: Embedder, store: MemoryStore) -> None:
        self._embedder = embedder
        self._store = store

    def read(self, agent_id: UUID, query: str, *, top_k: int) -> tuple[MemoryHit, ...]:
        if not query.strip() or top_k < 1:
            return ()
        query_embedding = self._embedder.embed([query])[0]
        return self._store.search(
            agent_id,
            query_embedding,
            embed_model_id=self._embedder.model_id,
            embed_dim=self._embedder.dim,
            top_k=top_k,
        )
