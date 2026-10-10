"""spec 0004 2.6 (P3-4): `aether_memory` outbound 포트(`Embedder`·`MemoryStore`)의 공용 fake.

`tests/arch/test_fake_duplication.py`(improvement-log 2026-09-28-001)가 같은 포트의 fake 가
여러 파일에 흩어지는 것을 막습니다 — `test_write_agent_memory.py` 와
`test_read_agent_memory.py` 가 이 둘을 같이 씁니다. 테스트 지원 코드이며 제품 코드가
아닙니다.
"""

from __future__ import annotations

import uuid

from aether_memory.domain.memory import MemoryHit, NewMemory


class FakeEmbedder:
    """`Embedder` 의 결정적 fake — 글자 수를 첫 성분으로 하는 3차원 벡터. 호출을 기록합니다."""

    model_id = "fake-embed"
    dim = 3

    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    def embed(self, texts: list[str]) -> list[list[float]]:
        self.calls.append(list(texts))
        return [[float(len(text)), 1.0, 0.0] for text in texts]


class FakeMemoryStore:
    """`MemoryStore` 의 인메모리 fake — `add`·`search` 호출을 기록하고, `search` 는 미리
    준비된 `hits` 를 그대로 돌려줍니다."""

    def __init__(self, hits: tuple[MemoryHit, ...] = ()) -> None:
        self.added: list[NewMemory] = []
        self.searches: list[tuple[uuid.UUID, list[float], str, int, int]] = []
        self.hits = hits

    def add(self, memory: NewMemory) -> None:
        self.added.append(memory)

    def search(
        self,
        agent_id: uuid.UUID,
        query_embedding: list[float],
        *,
        embed_model_id: str,
        embed_dim: int,
        top_k: int = 3,
    ) -> tuple[MemoryHit, ...]:
        self.searches.append((agent_id, query_embedding, embed_model_id, embed_dim, top_k))
        return self.hits
