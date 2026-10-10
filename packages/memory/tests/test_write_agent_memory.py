"""spec 0004 2.6, D-9 (P3-4): `WriteAgentMemoryUseCase` 의 계약 테스트. 컨테이너 없음 —
`Embedder`·`MemoryStore` outbound 포트에 fake 를 꽂습니다(AR-9).
"""

from __future__ import annotations

import uuid
from pathlib import Path

from aether_memory.application.usecases.write_agent_memory import WriteAgentMemoryUseCase
from aether_memory.domain.memory import NewMemory

from tests.support.memory_fakes import FakeEmbedder, FakeMemoryStore

_AGENT = uuid.UUID("00000000-0000-0000-0000-0000000000a1")
_RUN = uuid.UUID("00000000-0000-0000-0000-0000000000b1")


def test_write_embeds_content_and_stores_one_entry_with_model_identity() -> None:
    """spec 2.6, D-9: 본문 그대로 한 건, 임베딩과 모델 id·차원을 함께 저장합니다."""
    embedder, store = FakeEmbedder(), FakeMemoryStore()

    WriteAgentMemoryUseCase(embedder, store).write(_AGENT, _RUN, "  the answer is 42  ")

    assert embedder.calls == [["  the answer is 42  "]]
    assert store.added == [
        NewMemory(
            agent_id=_AGENT,
            run_id=_RUN,
            content="  the answer is 42  ",
            embedding=(float(len("  the answer is 42  ")), 1.0, 0.0),
            embed_model_id="fake-embed",
            embed_dim=3,
        )
    ]


def test_write_skips_blank_content_without_embedding() -> None:
    """P3-4 (c): 본문이 비어 있으면 쓰지 않습니다(임베딩도 부르지 않음)."""
    embedder, store = FakeEmbedder(), FakeMemoryStore()
    usecase = WriteAgentMemoryUseCase(embedder, store)

    usecase.write(_AGENT, _RUN, "real")  # 대조: 비지 않으면 쓴다
    assert len(store.added) == 1
    usecase.write(_AGENT, _RUN, "")
    usecase.write(_AGENT, _RUN, "   \n\t")

    assert len(store.added) == 1
    assert embedder.calls == [["real"]]


def test_postgres_memory_adapter_never_touches_knowledge_chunks() -> None:
    """spec R-10: Memory 어댑터의 쿼리는 `knowledge_chunks` 를 참조하지 않습니다 —
    한 쿼리로 합치지 않습니다."""
    import aether_memory.adapters.outbound.memory_store.postgres as adapter

    source = Path(adapter.__file__).read_text(encoding="utf-8")
    assert "data.agent_memory" in source  # 대조: 올바른 파일을 읽고 있다
    assert "knowledge_chunks" not in source
