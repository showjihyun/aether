"""spec 0004 R-5, D-9, C-3 (P3-2b): `PostgresKnowledgeStore` + `IngestKnowledgeUseCase`
의 통합 테스트 — pgvector testcontainer.

`tests/support/pg.py` 의 공유 컨테이너(세션 1개, `tests/support/pg.py` 참조,
budget 주의사항)를 그대로 쓰고 새 fixture 를 만들지 않습니다. `data_connection_factory`
(aether_data 역할)로 `KnowledgeStore` 를, `admin_connection_factory` 로 `control.
knowledge_sets`/`knowledge_ingestions` 선언 행을 만듭니다(이 단위는 그 선언 경로의
PostgreSQL 어댑터를 아직 포함하지 않으므로 — api 쪽은 별도 단위 파일에서 자체
포트 계약 테스트로 검증합니다).
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from pathlib import Path

import psycopg
import pytest
from aether_context.adapters.outbound.connector.filesystem import FilesystemConnector
from aether_context.adapters.outbound.indexer.fixed_size import FixedSizeIndexer
from aether_context.adapters.outbound.knowledge_store.postgres import PostgresKnowledgeStore
from aether_context.application.ports.inbound.ingest_knowledge import IngestKnowledgeRequest
from aether_context.application.ports.outbound.knowledge_store import EmbeddingMismatch
from aether_context.application.usecases.ingest_knowledge import IngestKnowledgeUseCase
from aether_context.domain.knowledge import EmbeddedChunk

pytestmark = pytest.mark.integration

_EMBED_DIM = 768
_EMBED_MODEL_ID = "test-embed-model"


class _DeterministicHashEmbedder:
    """feature-hashing bag-of-words — 실제 네트워크 없이, 그러나 **단어 겹침이 실제로
    코사인 거리에 반영되는** 결정적 벡터입니다(R-5 가 "그 청크가 1위" 를 의미 있게
    판정하려면 임베딩이 최소한 어휘 겹침을 반영해야 합니다 — 순수 `sha256(전체 문자열)`
    은 그렇지 않아 처음에 이 테스트가 실패했습니다, 아래 red 증거 참조)."""

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


def test_ingest_three_documents_then_search_unique_sentence_ranks_first(
    tmp_path: Path,
    admin_connection_factory: Callable[[], psycopg.Connection],
    data_connection_factory: Callable[[], psycopg.Connection],
) -> None:
    """spec R-5: 디렉터리 하나(문서 3개)를 적재하면, 그중 하나의 고유 문장으로
    검색했을 때 그 청크가 1위로 나옵니다."""
    (tmp_path / "alpha.txt").write_text(
        "This document talks about apples and orchards in general terms.",
        encoding="utf-8",
    )
    (tmp_path / "beta.txt").write_text(
        "The quokka is a small marsupial found only on Rottnest Island near Perth.",
        encoding="utf-8",
    )
    (tmp_path / "gamma.txt").write_text(
        "Quarterly revenue figures are discussed in this unrelated finance memo.",
        encoding="utf-8",
    )

    admin_conn = admin_connection_factory()
    try:
        knowledge_set_id = _insert_knowledge_set(admin_conn, f"set-{uuid.uuid4()}")
        ingestion_id = _insert_ingestion(admin_conn, knowledge_set_id, str(tmp_path))
    finally:
        admin_conn.close()

    store = PostgresKnowledgeStore(data_connection_factory)
    usecase = IngestKnowledgeUseCase(
        FilesystemConnector(),
        FixedSizeIndexer(chunk_chars=1000, overlap_chars=200),
        _DeterministicHashEmbedder(),
        store,
    )
    result = usecase(
        IngestKnowledgeRequest(
            knowledge_set_id=knowledge_set_id, ingestion_id=ingestion_id, source=str(tmp_path)
        )
    )
    assert result.chunk_count == 3  # 세 문서 각각 1000자 미만 -> 청크 1개씩

    embedder = _DeterministicHashEmbedder()
    query_vector = embedder.embed(["quokka marsupial Rottnest Island"])[0]
    results = store.search(
        (knowledge_set_id,),
        query_vector,
        embed_model_id=_EMBED_MODEL_ID,
        embed_dim=_EMBED_DIM,
        top_k=5,
    )

    assert len(results) == 3
    assert results[0].source_path == "beta.txt"


def test_search_with_mismatched_model_or_dim_requires_reingestion(
    tmp_path: Path,
    admin_connection_factory: Callable[[], psycopg.Connection],
    data_connection_factory: Callable[[], psycopg.Connection],
) -> None:
    """spec D-9, C-3: 저장된 청크의 임베딩 모델·차원과 질의가 다르면 검색은 조용히
    섞지 않고 `EmbeddingMismatch` 로 재적재를 요구합니다."""
    (tmp_path / "doc.txt").write_text("irrelevant content for mismatch test", encoding="utf-8")

    admin_conn = admin_connection_factory()
    try:
        knowledge_set_id = _insert_knowledge_set(admin_conn, f"set-{uuid.uuid4()}")
        ingestion_id = _insert_ingestion(admin_conn, knowledge_set_id, str(tmp_path))
    finally:
        admin_conn.close()

    store = PostgresKnowledgeStore(data_connection_factory)
    usecase = IngestKnowledgeUseCase(
        FilesystemConnector(),
        FixedSizeIndexer(chunk_chars=1000, overlap_chars=200),
        _DeterministicHashEmbedder(),
        store,
    )
    usecase(
        IngestKnowledgeRequest(
            knowledge_set_id=knowledge_set_id, ingestion_id=ingestion_id, source=str(tmp_path)
        )
    )

    with pytest.raises(EmbeddingMismatch):
        store.search(
            (knowledge_set_id,),
            [0.0] * _EMBED_DIM,
            embed_model_id="a-different-model",
            embed_dim=_EMBED_DIM,
        )


def test_search_with_tied_distance_orders_deterministically_by_source_path_and_chunk_index(
    admin_connection_factory: Callable[[], psycopg.Connection],
    data_connection_factory: Callable[[], psycopg.Connection],
) -> None:
    """spec R-1 (2026-10-09 실측 결함): `ORDER BY distance ASC` 뿐이면 거리가 같은
    청크 둘의 순서가 PostgreSQL 의 물리적 저장 순서에 달려 있어 "같은 입력에 같은
    출력"(R-1)이 구조적으로 깨집니다. **같은 임베딩**을 가진 청크 둘(`z-doc.txt`
    청크 하나, `a-doc.txt` 청크 하나 — `source_path` 알파벳 역순으로 insert)을
    넣어, 거리가 완전히 같을 때도 순서가 `source_path`(그리고 `chunk_index`)로
    고정되는지 봅니다."""
    admin_conn = admin_connection_factory()
    try:
        knowledge_set_id = _insert_knowledge_set(admin_conn, f"set-{uuid.uuid4()}")
        ingestion_id = _insert_ingestion(admin_conn, knowledge_set_id, "tie-break-fixture")
    finally:
        admin_conn.close()

    tied_embedding = tuple([1.0] + [0.0] * (_EMBED_DIM - 1))
    store = PostgresKnowledgeStore(data_connection_factory)
    # alphabetically-later source_path 를 먼저 insert 합니다 — 물리적 저장 순서가
    # source_path 순서와 일치하면 이 결함을 재현하지 못하므로, 역순으로 넣습니다.
    store.replace_chunks(
        knowledge_set_id,
        ingestion_id,
        (
            EmbeddedChunk(
                source_path="z-doc.txt",
                chunk_index=0,
                content="z content",
                embedding=tied_embedding,
                embed_model_id=_EMBED_MODEL_ID,
                embed_dim=_EMBED_DIM,
            ),
            EmbeddedChunk(
                source_path="a-doc.txt",
                chunk_index=0,
                content="a content",
                embedding=tied_embedding,
                embed_model_id=_EMBED_MODEL_ID,
                embed_dim=_EMBED_DIM,
            ),
        ),
    )

    results = [
        store.search(
            (knowledge_set_id,),
            list(tied_embedding),
            embed_model_id=_EMBED_MODEL_ID,
            embed_dim=_EMBED_DIM,
            top_k=5,
        )
        for _ in range(5)
    ]
    first = results[0]
    assert len(first) == 2
    assert first[0].source_path == "a-doc.txt"
    assert first[1].source_path == "z-doc.txt"
    for other in results[1:]:
        assert tuple((r.source_path, r.chunk_index) for r in other) == tuple(
            (r.source_path, r.chunk_index) for r in first
        )
