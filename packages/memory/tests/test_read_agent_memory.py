"""spec 0004 2.6, D-9, R-1 (P3-4): `ReadAgentMemoryUseCase` 의 계약 테스트. 컨테이너 없음 —
`Embedder`·`MemoryStore` outbound 포트에 fake 를 꽂습니다(AR-9).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from aether_memory.application.usecases.read_agent_memory import ReadAgentMemoryUseCase
from aether_memory.domain.memory import MemoryEntry, MemoryHit

from tests.support.memory_fakes import FakeEmbedder, FakeMemoryStore

_AGENT = uuid.UUID("00000000-0000-0000-0000-0000000000a1")


def test_read_embeds_query_and_returns_store_hits_in_store_order() -> None:
    """spec 2.6: 질의를 임베딩해 Agent 단위로 검색하고 저장소가 정한 순서를 보존합니다."""
    created = datetime(2026, 10, 1, tzinfo=UTC)
    hits = tuple(
        MemoryHit(
            entry=MemoryEntry(
                id=uuid.UUID(int=n),
                agent_id=_AGENT,
                run_id=None,
                content=f"m{n}",
                created_at=created,
            ),
            score=0.1 * n,
        )
        for n in (2, 1, 3)
    )
    embedder, store = FakeEmbedder(), FakeMemoryStore(hits)

    result = ReadAgentMemoryUseCase(embedder, store).read(_AGENT, "query", top_k=4)

    assert result == hits
    assert store.searches == [(_AGENT, [5.0, 1.0, 0.0], "fake-embed", 3, 4)]


def test_read_with_blank_query_or_nonpositive_top_k_returns_nothing() -> None:
    embedder, store = FakeEmbedder(), FakeMemoryStore()
    usecase = ReadAgentMemoryUseCase(embedder, store)

    usecase.read(_AGENT, "ok", top_k=1)  # 대조: 정상 입력은 검색한다
    assert len(store.searches) == 1
    assert usecase.read(_AGENT, "   ", top_k=3) == ()
    assert usecase.read(_AGENT, "ok", top_k=0) == ()
    assert len(store.searches) == 1
