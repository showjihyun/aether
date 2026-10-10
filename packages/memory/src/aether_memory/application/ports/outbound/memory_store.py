"""spec 0004 2.6, 2.8, D-9, D-10, R-10 (P3-4): `MemoryStore` outbound 포트.

`data.agent_memory` 만 대상입니다 — Knowledge 의 저장소(`KnowledgeStore`)와 같은 표·같은
인덱스를 쓰지 않고, 한 쿼리로 합치지도 않습니다(R-10).
"""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from aether_memory.domain.memory import MemoryHit, NewMemory

DEFAULT_TOP_K = 3
"""읽기의 상위 k 기본값. `aether_context` 의 `_DEFAULT_MEMORY_TOP_K` 와 같은 숫자
(패키지 사이를 import 하지 않고 숫자만 맞춥니다)."""


class MemoryStore(Protocol):
    def add(self, memory: NewMemory) -> None:
        """기억 한 건을 추가합니다."""
        ...

    def search(
        self,
        agent_id: UUID,
        query_embedding: list[float],
        *,
        embed_model_id: str,
        embed_dim: int,
        top_k: int = DEFAULT_TOP_K,
    ) -> tuple[MemoryHit, ...]:
        """`agent_id` 의 기억 중, 같은 임베딩 모델(`embed_model_id`·`embed_dim`)로 만든 것만
        대상으로 가까운 순 상위 `top_k`. 거리가 같으면 `created_at` 내림차순, 그래도
        같으면 `id` 오름차순 — 결정적입니다(R-1)."""
        ...
