"""spec 0004 2.6, 2.8, D-9, D-10, R-1, R-10 (P3-4): `PostgresMemoryStore` —
`data.agent_memory` 의 pgvector 구현. pgvector testcontainer, `aether_data` 역할.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

import psycopg
import pytest
from aether_memory.adapters.outbound.memory_store.postgres import PostgresMemoryStore
from aether_memory.application.usecases.read_agent_memory import ReadAgentMemoryUseCase
from aether_memory.application.usecases.write_agent_memory import WriteAgentMemoryUseCase
from aether_memory.domain.memory import NewMemory

pytestmark = pytest.mark.integration

_DIM = 768
_MODEL = "test-embed-model"


class _HashEmbedder:
    """어휘 겹침이 코사인 거리에 반영되는 결정적 임베더(Knowledge 통합 테스트와 같은 모양)."""

    model_id = _MODEL
    dim = _DIM

    def embed(self, texts: list[str]) -> list[list[float]]:
        import hashlib
        import math
        import re

        vectors: list[list[float]] = []
        for text in texts:
            vector = [0.0] * self.dim
            for word in re.findall(r"[a-zA-Z]+", text.lower()):
                bucket = int(hashlib.sha256(word.encode("utf-8")).hexdigest(), 16) % self.dim
                vector[bucket] += 1.0
            norm = math.sqrt(sum(v * v for v in vector)) or 1.0
            vectors.append([v / norm for v in vector])
        return vectors


def _literal(values: list[float] | tuple[float, ...]) -> str:
    return "[" + ",".join(repr(float(v)) for v in values) + "]"


def _insert_agent(admin_connection_factory: Callable[[], psycopg.Connection]) -> uuid.UUID:
    conn = admin_connection_factory()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO control.agents (name) VALUES (%s) RETURNING id",
                (f"mem-agent-{uuid.uuid4()}",),
            )
            row = cur.fetchone()
            assert row is not None
            agent_id: uuid.UUID = row[0]
        conn.commit()
    finally:
        conn.close()
    return agent_id


def _insert_run(
    admin_connection_factory: Callable[[], psycopg.Connection], agent_id: uuid.UUID
) -> uuid.UUID:
    conn = admin_connection_factory()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO control.agent_versions (agent_id, version, definition) "
                "VALUES (%s, 1, %s) RETURNING id",
                (agent_id, json.dumps({"schema_version": 1})),
            )
            row = cur.fetchone()
            assert row is not None
            cur.execute(
                "INSERT INTO control.runs (agent_version_id, input) VALUES (%s, %s) RETURNING id",
                (row[0], "x"),
            )
            run_row = cur.fetchone()
            assert run_row is not None
            run_id: uuid.UUID = run_row[0]
        conn.commit()
    finally:
        conn.close()
    return run_id


def _raw_insert(
    data_connection_factory: Callable[[], psycopg.Connection],
    *,
    memory_id: uuid.UUID,
    agent_id: uuid.UUID,
    content: str,
    created_at: datetime,
    embedding: list[float],
    model_id: str = _MODEL,
) -> None:
    with data_connection_factory() as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO data.agent_memory
                (id, agent_id, content, embed_model_id, embed_dim, created_at, embedding)
            VALUES (%s, %s, %s, %s, %s, %s, %s::vector)
            """,
            (memory_id, agent_id, content, model_id, _DIM, created_at, _literal(embedding)),
        )


def test_write_then_read_roundtrip_with_run_fk(
    admin_connection_factory: Callable[[], psycopg.Connection],
    data_connection_factory: Callable[[], psycopg.Connection],
) -> None:
    """spec 2.6, 2.8: 쓴 기억을 같은 Agent 의 질의로 읽습니다(run_id FK 포함)."""
    agent_id = _insert_agent(admin_connection_factory)
    run_id = _insert_run(admin_connection_factory, agent_id)
    store = PostgresMemoryStore(data_connection_factory)
    embedder = _HashEmbedder()

    WriteAgentMemoryUseCase(embedder, store).write(
        agent_id, run_id, "The quokka lives on Rottnest Island."
    )
    hits = ReadAgentMemoryUseCase(embedder, store).read(agent_id, "quokka Rottnest Island", top_k=3)

    assert len(hits) == 1
    entry = hits[0].entry
    assert entry.agent_id == agent_id and entry.run_id == run_id
    assert entry.content == "The quokka lives on Rottnest Island."
    assert entry.created_at.tzinfo is not None
    assert 0.0 < hits[0].score < 0.5  # 실제 코사인 거리(어휘 일부만 겹침)


def test_read_is_scoped_to_agent(
    admin_connection_factory: Callable[[], psycopg.Connection],
    data_connection_factory: Callable[[], psycopg.Connection],
) -> None:
    """spec 2.6 (Agent 단위): 다른 Agent 의 기억은 같은 질의에도 보이지 않습니다."""
    mine = _insert_agent(admin_connection_factory)
    other = _insert_agent(admin_connection_factory)
    store = PostgresMemoryStore(data_connection_factory)
    embedder = _HashEmbedder()
    WriteAgentMemoryUseCase(embedder, store).write(other, None, "secret orchid launch code")

    reader = ReadAgentMemoryUseCase(embedder, store)
    assert reader.read(mine, "orchid launch code", top_k=5) == ()
    assert len(reader.read(other, "orchid launch code", top_k=5)) == 1


def test_read_ranks_closer_first_and_respects_top_k(
    admin_connection_factory: Callable[[], psycopg.Connection],
    data_connection_factory: Callable[[], psycopg.Connection],
) -> None:
    """spec R-1: 실제 pgvector 에서 가까운 것이 먼저, 상위 k 만."""
    agent_id = _insert_agent(admin_connection_factory)
    store = PostgresMemoryStore(data_connection_factory)
    embedder = _HashEmbedder()
    writer = WriteAgentMemoryUseCase(embedder, store)
    writer.write(agent_id, None, "alpha beta gamma delta")
    writer.write(agent_id, None, "alpha beta")
    writer.write(agent_id, None, "zeta eta theta")

    reader = ReadAgentMemoryUseCase(embedder, store)
    hits = reader.read(agent_id, "alpha beta", top_k=2)

    assert [h.entry.content for h in hits] == ["alpha beta", "alpha beta gamma delta"]
    assert hits[0].score <= hits[1].score


def test_read_ties_are_broken_by_created_at_desc_then_id_asc(
    admin_connection_factory: Callable[[], psycopg.Connection],
    data_connection_factory: Callable[[], psycopg.Connection],
) -> None:
    """spec R-1 (P3-3 의 Knowledge 동점 결함과 같은 부류): 거리가 같으면 `created_at
    DESC, id ASC` 로 결정적입니다. 같은 벡터 넷을 일부러 뒤섞인 id·시각으로 심습니다."""
    agent_id = _insert_agent(admin_connection_factory)
    embedder = _HashEmbedder()
    vector = embedder.embed(["tie tie tie"])[0]
    base = datetime(2026, 10, 1, 12, 0, 0, tzinfo=UTC)
    older, newer = base, base + timedelta(hours=1)
    ids = [uuid.UUID(int=n) for n in (0x30, 0x10, 0x20, 0x05)]
    seeded = [(ids[0], older), (ids[1], newer), (ids[2], newer), (ids[3], older)]
    for memory_id, created_at in seeded:
        _raw_insert(
            data_connection_factory,
            memory_id=memory_id,
            agent_id=agent_id,
            content=f"tie-{memory_id.int:x}",
            created_at=created_at,
            embedding=vector,
        )
    # 기대 순서: 최신 시각 중 id 오름차순(0x10, 0x20), 그다음 오래된 것 중 id 오름차순(0x05, 0x30).
    expected = [ids[1], ids[2], ids[3], ids[0]]

    store = PostgresMemoryStore(data_connection_factory)
    reader = ReadAgentMemoryUseCase(embedder, store)
    for _ in range(5):
        hits = reader.read(agent_id, "tie tie tie", top_k=10)
        assert [h.entry.id for h in hits] == expected


def test_read_ignores_memory_embedded_with_another_model(
    admin_connection_factory: Callable[[], psycopg.Connection],
    data_connection_factory: Callable[[], psycopg.Connection],
) -> None:
    """spec D-9: 다른 임베딩 모델로 만든 기억은 같은 공간에 있지 않으므로 비교하지
    않습니다(조용히 제외 — 기억은 부산물이라 재적재를 요구하지 않습니다)."""
    agent_id = _insert_agent(admin_connection_factory)
    embedder = _HashEmbedder()
    vector = embedder.embed(["same words here"])[0]
    now = datetime(2026, 10, 1, tzinfo=UTC)
    _raw_insert(
        data_connection_factory,
        memory_id=uuid.uuid4(),
        agent_id=agent_id,
        content="current",
        created_at=now,
        embedding=vector,
    )
    _raw_insert(
        data_connection_factory,
        memory_id=uuid.uuid4(),
        agent_id=agent_id,
        content="stale",
        created_at=now,
        embedding=vector,
        model_id="some-older-model",
    )

    hits = ReadAgentMemoryUseCase(embedder, PostgresMemoryStore(data_connection_factory)).read(
        agent_id, "same words here", top_k=5
    )

    assert [h.entry.content for h in hits] == ["current"]


def test_add_persists_model_identity(
    admin_connection_factory: Callable[[], psycopg.Connection],
    data_connection_factory: Callable[[], psycopg.Connection],
) -> None:
    """spec D-9: 저장 행에 임베딩 모델 id·차원이 남습니다."""
    agent_id = _insert_agent(admin_connection_factory)
    embedder = _HashEmbedder()
    PostgresMemoryStore(data_connection_factory).add(
        NewMemory(
            agent_id=agent_id,
            run_id=None,
            content="persist me",
            embedding=tuple(embedder.embed(["persist me"])[0]),
            embed_model_id=_MODEL,
            embed_dim=_DIM,
        )
    )

    with data_connection_factory() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT content, embed_model_id, embed_dim FROM data.agent_memory WHERE agent_id = %s",
            (agent_id,),
        )
        assert cur.fetchall() == [("persist me", _MODEL, _DIM)]
