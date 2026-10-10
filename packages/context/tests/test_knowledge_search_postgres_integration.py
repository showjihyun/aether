"""spec 0004 2.4, 2.5, D-5, R-9 (P3-3): `PostgresKnowledgeSearch` — 이름 해석 + 질의
임베딩 + `KnowledgeStore.search`. pgvector testcontainer.

핵심 판정은 R-9 "바인딩되지 않은 집합은 검색되지 않습니다" — 두 Knowledge Set 에
서로 다른 내용을 적재하고, 이름 하나만 건넸을 때 다른 집합의 내용이 결과에
새어나오지 않는지 봅니다.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from pathlib import Path

import psycopg
import pytest
from aether_context.adapters.outbound.connector.filesystem import FilesystemConnector
from aether_context.adapters.outbound.indexer.fixed_size import FixedSizeIndexer
from aether_context.adapters.outbound.knowledge_search.postgres import PostgresKnowledgeSearch
from aether_context.adapters.outbound.knowledge_store.postgres import PostgresKnowledgeStore
from aether_context.application.ports.inbound.ingest_knowledge import IngestKnowledgeRequest
from aether_context.application.usecases.ingest_knowledge import IngestKnowledgeUseCase

pytestmark = pytest.mark.integration

_EMBED_DIM = 768
_EMBED_MODEL_ID = "test-embed-model"


class _DeterministicHashEmbedder:
    """`test_postgres_knowledge_store_integration.py` 의 것과 같은 모양 — 어휘
    겹침이 코사인 거리에 반영되는 결정적 임베더."""

    model_id = _EMBED_MODEL_ID
    dim = _EMBED_DIM

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


def _insert_knowledge_set(conn: psycopg.Connection, name: str) -> uuid.UUID:
    with conn.cursor() as cur:
        cur.execute("INSERT INTO control.knowledge_sets (name) VALUES (%s) RETURNING id", (name,))
        row = cur.fetchone()
        assert row is not None
        set_id: uuid.UUID = row[0]
    conn.commit()
    return set_id


def _insert_ingestion(
    conn: psycopg.Connection, knowledge_set_id: uuid.UUID, source: str
) -> uuid.UUID:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO control.knowledge_ingestions (knowledge_set_id, source)
            VALUES (%s, %s) RETURNING id
            """,
            (knowledge_set_id, source),
        )
        row = cur.fetchone()
        assert row is not None
        ingestion_id: uuid.UUID = row[0]
    conn.commit()
    return ingestion_id


def _ingest(
    tmp_path: Path,
    text: str,
    admin_connection_factory: Callable[[], psycopg.Connection],
    data_connection_factory: Callable[[], psycopg.Connection],
    set_name: str,
) -> None:
    (tmp_path / "doc.txt").write_text(text, encoding="utf-8")
    admin_conn = admin_connection_factory()
    try:
        knowledge_set_id = _insert_knowledge_set(admin_conn, set_name)
        ingestion_id = _insert_ingestion(admin_conn, knowledge_set_id, str(tmp_path))
    finally:
        admin_conn.close()

    usecase = IngestKnowledgeUseCase(
        FilesystemConnector(),
        FixedSizeIndexer(chunk_chars=1000, overlap_chars=200),
        _DeterministicHashEmbedder(),
        PostgresKnowledgeStore(data_connection_factory),
    )
    usecase(
        IngestKnowledgeRequest(
            knowledge_set_id=knowledge_set_id, ingestion_id=ingestion_id, source=str(tmp_path)
        )
    )


def test_search_only_sees_bound_set_names_not_other_sets(
    tmp_path: Path,
    admin_connection_factory: Callable[[], psycopg.Connection],
    data_connection_factory: Callable[[], psycopg.Connection],
) -> None:
    """spec R-9: 이름을 건네지 않은 집합은 그 집합에 아무리 관련 있는 내용이
    있어도 결과에 나타나지 않습니다."""
    bound_name = f"bound-{uuid.uuid4()}"
    other_name = f"other-{uuid.uuid4()}"

    bound_dir = tmp_path / "bound"
    bound_dir.mkdir()
    other_dir = tmp_path / "other"
    other_dir.mkdir()

    _ingest(
        bound_dir,
        "The quokka is a small marsupial found on Rottnest Island.",
        admin_connection_factory,
        data_connection_factory,
        bound_name,
    )
    _ingest(
        other_dir,
        "The quokka is a small marsupial found on Rottnest Island.",
        admin_connection_factory,
        data_connection_factory,
        other_name,
    )

    search = PostgresKnowledgeSearch(data_connection_factory, _DeterministicHashEmbedder())
    results = search.search((bound_name,), "quokka marsupial Rottnest Island", top_k=5)

    assert len(results) == 1
    assert results[0].source_path == "doc.txt"


def test_search_with_unknown_set_name_returns_empty(
    data_connection_factory: Callable[[], psycopg.Connection],
) -> None:
    """spec R-9: 존재하지 않는(바인딩되지 않은) 이름은 조용히 빈 결과입니다."""
    search = PostgresKnowledgeSearch(data_connection_factory, _DeterministicHashEmbedder())
    results = search.search((f"no-such-set-{uuid.uuid4()}",), "anything", top_k=5)
    assert results == ()
