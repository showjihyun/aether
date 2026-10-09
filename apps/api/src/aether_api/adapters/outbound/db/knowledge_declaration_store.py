"""spec 0004 2.4, 2.8, D-4: `KnowledgeDeclarationStore` 의 PostgreSQL 구현.

`connect` 는 연결 **팩토리**(`PostgresRunDeclarationStore` 와 같은 패턴, spec 0001
H-3) — 메서드마다 새 연결을 열고 `with connect() as conn:` 이 커밋·롤백·닫기를
맡깁니다. `aether_control` 역할로 접속합니다(마이그레이션 0004 GRANT).
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from uuid import UUID

import psycopg

from aether_api.domain.knowledge import (
    IngestionStatus,
    KnowledgeIngestionView,
    KnowledgeSetView,
)

_INGESTION_COLUMNS = (
    "id, knowledge_set_id, source, status, requested_at, started_at, finished_at, failure_reason"
)


def _ingestion_row_to_view(row: tuple) -> KnowledgeIngestionView:  # type: ignore[type-arg]
    (
        ingestion_id,
        knowledge_set_id,
        source,
        status,
        requested_at,
        started_at,
        finished_at,
        failure_reason,
    ) = row
    return KnowledgeIngestionView(
        id=ingestion_id,
        knowledge_set_id=knowledge_set_id,
        source=source,
        status=status,
        requested_at=requested_at,
        started_at=started_at,
        finished_at=finished_at,
        failure_reason=failure_reason,
    )


class PostgresKnowledgeDeclarationStore:
    """`control.knowledge_sets`/`control.knowledge_ingestions` 에 대한 outbound 포트
    `KnowledgeDeclarationStore` 의 PostgreSQL 구현."""

    def __init__(self, connect: Callable[[], psycopg.Connection]) -> None:
        self._connect = connect

    def create_set(self, name: str) -> KnowledgeSetView:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                "INSERT INTO control.knowledge_sets (name) VALUES (%s) "
                "RETURNING id, name, created_at",
                (name,),
            )
            row = cur.fetchone()
        if row is None:  # pragma: no cover - INSERT ... RETURNING always yields a row
            raise RuntimeError("INSERT ... RETURNING control.knowledge_sets returned no row")
        set_id, set_name, created_at = row
        return KnowledgeSetView(id=set_id, name=set_name, created_at=created_at)

    def get_set(self, knowledge_set_id: UUID) -> KnowledgeSetView | None:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT id, name, created_at FROM control.knowledge_sets WHERE id = %s",
                (knowledge_set_id,),
            )
            row = cur.fetchone()
        if row is None:
            return None
        set_id, name, created_at = row
        return KnowledgeSetView(id=set_id, name=name, created_at=created_at)

    def create_ingestion(self, knowledge_set_id: UUID, source: str) -> KnowledgeIngestionView:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO control.knowledge_ingestions (knowledge_set_id, source)
                VALUES (%s, %s)
                RETURNING id, status, requested_at
                """,
                (knowledge_set_id, source),
            )
            row = cur.fetchone()
        if row is None:  # pragma: no cover
            raise RuntimeError("INSERT ... RETURNING control.knowledge_ingestions returned no row")
        ingestion_id, status, requested_at = row
        return KnowledgeIngestionView(
            id=ingestion_id,
            knowledge_set_id=knowledge_set_id,
            source=source,
            status=status,
            requested_at=requested_at,
            started_at=None,
            finished_at=None,
            failure_reason=None,
        )

    def get_ingestion(self, ingestion_id: UUID) -> KnowledgeIngestionView | None:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                f"SELECT {_INGESTION_COLUMNS} FROM control.knowledge_ingestions WHERE id = %s",
                (ingestion_id,),
            )
            row = cur.fetchone()
        if row is None:
            return None
        return _ingestion_row_to_view(row)

    def apply_ingestion_status(
        self,
        ingestion_id: UUID,
        *,
        status: IngestionStatus,
        started_at: datetime | None,
        finished_at: datetime | None,
        failure_reason: str | None,
    ) -> bool:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                UPDATE control.knowledge_ingestions
                SET status = %(status)s,
                    started_at = COALESCE(%(started_at)s, started_at),
                    finished_at = COALESCE(%(finished_at)s, finished_at),
                    failure_reason = COALESCE(%(failure_reason)s, failure_reason)
                WHERE id = %(ingestion_id)s
                RETURNING id
                """,
                {
                    "ingestion_id": ingestion_id,
                    "status": status,
                    "started_at": started_at,
                    "finished_at": finished_at,
                    "failure_reason": failure_reason,
                },
            )
            updated = cur.fetchone()
        return updated is not None
