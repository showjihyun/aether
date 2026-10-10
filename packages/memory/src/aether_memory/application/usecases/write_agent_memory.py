"""spec 0004 2.6, D-9 (P3-4): `WriteAgentMemoryUseCase` — `WriteAgentMemory` 의 구현.

본문을 가공하지 않습니다(요약·분할 없음). 임베딩과 함께 모델 id·차원을 저장합니다 —
읽을 때 같은 모델의 기억만 비교하기 위해서입니다.
"""

from __future__ import annotations

from uuid import UUID

from aether_memory.application.ports.outbound.embedder import Embedder
from aether_memory.application.ports.outbound.memory_store import MemoryStore
from aether_memory.domain.memory import NewMemory


class WriteAgentMemoryUseCase:
    def __init__(self, embedder: Embedder, store: MemoryStore) -> None:
        self._embedder = embedder
        self._store = store

    def write(self, agent_id: UUID, run_id: UUID | None, content: str) -> None:
        if not content.strip():
            return
        embedding = self._embedder.embed([content])[0]
        self._store.add(
            NewMemory(
                agent_id=agent_id,
                run_id=run_id,
                content=content,
                embedding=tuple(embedding),
                embed_model_id=self._embedder.model_id,
                embed_dim=self._embedder.dim,
            )
        )
