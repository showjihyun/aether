"""spec 0003 2.14, D-14 (🔒 P2-4): `ToolPermissionStore` 의 PostgreSQL 구현.

`connect` 는 연결 **팩토리**입니다(`PostgresApiKeyStore` 와 같은 패턴) — 메서드마다
새 연결을 열고 `with connect() as conn:` 이 커밋·롤백·닫기를 맡깁니다. 조립(`main.py`)이
건네는 `connect` 는 `Settings.psycopg_dsn`(운영에서 `aether_control` 역할)로 접속합니다
— 정책 표를 쓰는 것은 이 역할뿐입니다(spec C-7).
"""

from __future__ import annotations

from collections.abc import Callable
from uuid import UUID

import psycopg
from aether_policy.domain.decision import Decision


class PostgresToolPermissionStore:
    def __init__(self, connect: Callable[[], psycopg.Connection]) -> None:
        self._connect = connect

    def upsert(
        self, agent_version_id: UUID, server_name: str, tool_name: str, decision: Decision
    ) -> None:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO control.tool_permissions
                    (agent_version_id, server_name, tool_name, decision)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (agent_version_id, server_name, tool_name)
                DO UPDATE SET decision = EXCLUDED.decision
                """,
                (agent_version_id, server_name, tool_name, decision),
            )
