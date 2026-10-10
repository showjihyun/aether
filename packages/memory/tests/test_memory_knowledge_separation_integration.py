"""spec 0004 R-10, D-10 (P3-4): Memory 와 Knowledge 는 **다른 표·다른 인덱스**입니다.
코드가 아니라 DB 카탈로그(`pg_indexes`·`pg_class`·`pg_index`)를 조회해 판정합니다.
"""

from __future__ import annotations

from collections.abc import Callable

import psycopg
import pytest

pytestmark = pytest.mark.integration


def _indexes(conn: psycopg.Connection, table: str) -> dict[str, str]:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT indexname, indexdef FROM pg_indexes "
            "WHERE schemaname = 'data' AND tablename = %s ORDER BY indexname",
            (table,),
        )
        return {name: definition for name, definition in cur.fetchall()}


def _relation_oid(conn: psycopg.Connection, table: str) -> int:
    with conn.cursor() as cur:
        cur.execute("SELECT to_regclass(%s)::oid::int", (f"data.{table}",))
        row = cur.fetchone()
        assert row is not None and row[0] is not None
        oid: int = row[0]
        return oid


def test_agent_memory_and_knowledge_chunks_share_no_table_or_index(
    admin_connection_factory: Callable[[], psycopg.Connection],
) -> None:
    """spec R-10: 두 표는 서로 다른 relation 이고 인덱스 목록이 겹치지 않습니다."""
    conn = admin_connection_factory()
    try:
        memory = _indexes(conn, "agent_memory")
        knowledge = _indexes(conn, "knowledge_chunks")
        memory_oid = _relation_oid(conn, "agent_memory")
        knowledge_oid = _relation_oid(conn, "knowledge_chunks")
        with conn.cursor() as cur:
            cur.execute(
                "SELECT c.relname, i.indrelid::int FROM pg_index i "
                "JOIN pg_class c ON c.oid = i.indexrelid "
                "WHERE i.indrelid = ANY(%s)",
                ([memory_oid, knowledge_oid],),
            )
            owner_of = {name: table_oid for name, table_oid in cur.fetchall()}
    finally:
        conn.close()

    assert memory_oid != knowledge_oid
    # 각자 벡터 인덱스를 따로 가집니다(대조: 비어 있어서 우연히 겹치지 않는 게 아님).
    assert "ix_agent_memory_embedding_hnsw_cosine" in memory
    assert "ix_knowledge_chunks_embedding_hnsw_cosine" in knowledge
    assert memory.keys().isdisjoint(knowledge.keys())
    # 카탈로그 쪽에서도 어느 인덱스든 정확히 한 표에만 속합니다.
    assert {owner_of[name] for name in memory} == {memory_oid}
    assert {owner_of[name] for name in knowledge} == {knowledge_oid}
    # 정의 문자열이 상대 표를 가리키지 않습니다.
    assert all("agent_memory" in definition for definition in memory.values())
    assert all("knowledge_chunks" in definition for definition in knowledge.values())
