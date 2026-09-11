"""spec 0001 2.9 (H-3 설계 검토): `ApiKeyStore` 의 PostgreSQL 구현.

`connect` 는 연결 **팩토리**(`Callable[[], psycopg.Connection]`)입니다 — 메서드마다
새 연결을 열고 `with connect() as conn:` 블록이 커밋(성공 시)·롤백(예외 시)·닫기를
전부 맡습니다(psycopg3 의 `Connection.__exit__`). 조립(`main.py`)이 이 클래스를 만드는
시점에는 아직 연결을 열지 않습니다 — `create_app` 은 import 시 실행되고, DB 가 없는
테스트와 `aether-api openapi` 가 그 조립을 그대로 부르기 때문입니다. 커넥션 풀은
Phase 1 로 미룹니다.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from uuid import UUID

import psycopg

from aether_api.domain.api_key import ApiKey


class PostgresApiKeyStore:
    """`control.api_keys` 에 대한 outbound 포트 `ApiKeyStore` 의 PostgreSQL 구현."""

    def __init__(self, connect: Callable[[], psycopg.Connection]) -> None:
        self._connect = connect

    def find_by_hash(self, key_hash: str) -> ApiKey | None:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, label, key_hash, created_at, revoked_at
                FROM control.api_keys
                WHERE key_hash = %s
                """,
                (key_hash,),
            )
            row = cur.fetchone()
        if row is None:
            return None
        return _row_to_api_key(row)

    def create(self, label: str, key_hash: str) -> ApiKey:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO control.api_keys (label, key_hash)
                VALUES (%s, %s)
                RETURNING id, label, key_hash, created_at, revoked_at
                """,
                (label, key_hash),
            )
            row = cur.fetchone()
        if row is None:  # pragma: no cover - INSERT ... RETURNING always yields a row
            raise RuntimeError("INSERT ... RETURNING control.api_keys returned no row")
        return _row_to_api_key(row)

    def revoke(self, key_id: UUID) -> None:
        """멱등: 이미 폐기된 키는 `revoked_at` 을 유지합니다(`COALESCE`). 없는 id 는 `KeyError`."""
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                UPDATE control.api_keys
                SET revoked_at = COALESCE(revoked_at, now())
                WHERE id = %s
                RETURNING id
                """,
                (key_id,),
            )
            row = cur.fetchone()
        if row is None:
            raise KeyError(key_id)


def _row_to_api_key(row: tuple[UUID, str, str, datetime, datetime | None]) -> ApiKey:
    key_id, label, key_hash, created_at, revoked_at = row
    return ApiKey(
        id=key_id,
        label=label,
        key_hash=key_hash,
        created_at=created_at,
        revoked_at=revoked_at,
    )
