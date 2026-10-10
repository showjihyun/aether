"""spec 0004 2.6, 2.8, D-9, D-10, R-1, R-10 (P3-4): `MemoryStore` 포트의 pgvector 구현.

`data.agent_memory` **만** 봅니다 — 다른 표와 합치는 쿼리를 쓰지 않습니다(R-10).
`connect` 는 연결 팩토리입니다(`PostgresKnowledgeStore` 와 같은 패턴) — worker
(`aether_data` 역할)가 이 어댑터를 씁니다(마이그레이션 0004 가 그 역할에 이 표의
권한을 부여했습니다).

벡터는 `pgvector` 파이썬 패키지 없이 `"[0.1,0.2,...]"` 문자열을 `%s::vector` 로 캐스트합니다.
읽기는 같은 임베딩 모델(`embed_model_id`·`embed_dim`)로 만든 행만 비교합니다 — 다른
모델의 벡터는 같은 공간이 아닙니다. Knowledge 와 달리 불일치를 오류로 올리지 않고
조용히 제외합니다: 기억은 부산물이라 다시 적재하라고 요구할 대상이 아닙니다.
"""

from __future__ import annotations

from collections.abc import Callable
from uuid import UUID

import psycopg

from aether_memory.application.ports.outbound.memory_store import DEFAULT_TOP_K
from aether_memory.domain.memory import MemoryEntry, MemoryHit, NewMemory


def _vector_literal(values: tuple[float, ...] | list[float]) -> str:
    return "[" + ",".join(repr(float(value)) for value in values) + "]"


class PostgresMemoryStore:
    """`MemoryStore` 포트의 pgvector 구현(`data.agent_memory`)."""

    def __init__(self, connect: Callable[[], psycopg.Connection]) -> None:
        self._connect = connect

    def add(self, memory: NewMemory) -> None:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO data.agent_memory
                    (agent_id, run_id, content, embed_model_id, embed_dim, embedding)
                VALUES (%s, %s, %s, %s, %s, %s::vector)
                """,
                (
                    memory.agent_id,
                    memory.run_id,
                    memory.content,
                    memory.embed_model_id,
                    memory.embed_dim,
                    _vector_literal(memory.embedding),
                ),
            )

    def search(
        self,
        agent_id: UUID,
        query_embedding: list[float],
        *,
        embed_model_id: str,
        embed_dim: int,
        top_k: int = DEFAULT_TOP_K,
    ) -> tuple[MemoryHit, ...]:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, agent_id, run_id, content, created_at,
                       embedding <=> %s::vector AS distance
                FROM data.agent_memory
                WHERE agent_id = %s AND embed_model_id = %s AND embed_dim = %s
                ORDER BY distance ASC, created_at DESC, id ASC
                LIMIT %s
                """,
                (_vector_literal(query_embedding), agent_id, embed_model_id, embed_dim, top_k),
            )
            rows = cur.fetchall()
        return tuple(
            MemoryHit(
                entry=MemoryEntry(
                    id=row[0], agent_id=row[1], run_id=row[2], content=row[3], created_at=row[4]
                ),
                score=row[5],
            )
            for row in rows
        )
