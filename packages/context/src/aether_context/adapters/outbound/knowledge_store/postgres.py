"""spec 0004 2.4, 2.8, D-2, D-9, C-3, R-5: `KnowledgeStore` 포트의 pgvector 구현.

`connect` 는 연결 **팩토리**입니다(`PostgresRunDeclarationStore` 와 같은 패턴,
spec 0001 H-3) — 메서드마다 새 연결을 열고 `with connect() as conn:` 이 커밋·롤백·
닫기를 맡깁니다. worker(`aether_data` 역할)가 이 어댑터를 씁니다(spec 2.8 GRANT).

벡터는 `pgvector` 파이썬 패키지를 새 의존성으로 들이지 않습니다(마이그레이션 0004
와 같은 선택) — 임베딩을 `"[0.1,0.2,...]"` 문자열로 지어 `%s::vector` 로 캐스트합니다.

**재적재를 요구하는 오류(C-3, D-9).** `search` 는 먼저 대상 집합의 저장된
`embed_model_id`/`embed_dim` 을 조회해 질의와 다르면 `EmbeddingMismatch` 를 던지고,
실제 벡터 비교(`<=>`, 코사인 거리)는 하지 않습니다 — 다른 차원의 벡터를 비교하면
pgvector 자체가 오류를 내지만, 그 메시지는 "재적재하라" 는 의도를 담지 않으므로
애플리케이션 계층에서 먼저 판정합니다.
"""

from __future__ import annotations

from collections.abc import Callable
from uuid import UUID

import psycopg

from aether_context.application.ports.outbound.knowledge_store import (
    DEFAULT_TOP_K,
    EmbeddingMismatch,
)
from aether_context.domain.knowledge import EmbeddedChunk, SearchResult


def _vector_literal(values: tuple[float, ...] | list[float]) -> str:
    return "[" + ",".join(repr(float(value)) for value in values) + "]"


class PostgresKnowledgeStore:
    """`KnowledgeStore` 포트의 pgvector 구현(`data.knowledge_chunks`)."""

    def __init__(self, connect: Callable[[], psycopg.Connection]) -> None:
        self._connect = connect

    def replace_chunks(
        self,
        knowledge_set_id: UUID,
        ingestion_id: UUID,
        chunks: tuple[EmbeddedChunk, ...],
    ) -> None:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                "DELETE FROM data.knowledge_chunks WHERE knowledge_set_id = %s",
                (knowledge_set_id,),
            )
            for chunk in chunks:
                cur.execute(
                    """
                    INSERT INTO data.knowledge_chunks
                        (knowledge_set_id, ingestion_id, source_path, chunk_index,
                         content, embed_model_id, embed_dim, embedding)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s::vector)
                    """,
                    (
                        knowledge_set_id,
                        ingestion_id,
                        chunk.source_path,
                        chunk.chunk_index,
                        chunk.content,
                        chunk.embed_model_id,
                        chunk.embed_dim,
                        _vector_literal(chunk.embedding),
                    ),
                )

    def search(
        self,
        knowledge_set_ids: tuple[UUID, ...],
        query_embedding: list[float],
        *,
        embed_model_id: str,
        embed_dim: int,
        top_k: int = DEFAULT_TOP_K,
    ) -> tuple[SearchResult, ...]:
        if not knowledge_set_ids:
            return ()

        set_ids = list(knowledge_set_ids)
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT DISTINCT embed_model_id, embed_dim
                FROM data.knowledge_chunks
                WHERE knowledge_set_id = ANY(%s)
                """,
                (set_ids,),
            )
            for stored_model_id, stored_dim in cur.fetchall():
                if stored_model_id != embed_model_id or stored_dim != embed_dim:
                    raise EmbeddingMismatch(
                        requested_model_id=embed_model_id,
                        requested_dim=embed_dim,
                        stored_model_id=stored_model_id,
                        stored_dim=stored_dim,
                    )

            cur.execute(
                """
                SELECT source_path, chunk_index, content,
                       embedding <=> %s::vector AS distance
                FROM data.knowledge_chunks
                WHERE knowledge_set_id = ANY(%s)
                ORDER BY distance ASC, source_path ASC, chunk_index ASC
                LIMIT %s
                """,
                (_vector_literal(query_embedding), set_ids, top_k),
            )
            rows = cur.fetchall()
        return tuple(
            SearchResult(source_path=row[0], chunk_index=row[1], content=row[2], score=row[3])
            for row in rows
        )
