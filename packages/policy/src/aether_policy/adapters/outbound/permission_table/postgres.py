"""spec 0003 2.7, D-15, 개정 4: `PermissionTable` 의 PostgreSQL 구현 —
`control.tool_permissions` 을 SELECT 만 합니다.

`connect` 는 연결 **팩토리**입니다(`packages/mcp` 의 `PostgresAuditSink` 와 같은
패턴) — 메서드마다 새 연결을 열고 `with connect() as conn:` 이 커밋·롤백·닫기를
맡깁니다. 판정 시점의 호출자(Gateway, worker 프로세스)는 `aether_data` 역할로
접속합니다(D-15) — 그 역할은 이 표에 SELECT 만 가지고 있으므로, 이 클래스가 쓰기를
시도하면 DB 가 `InsufficientPrivilege` 로 거부합니다(정책 표를 쓰는 것은 여전히
`aether_control` 뿐, spec C-7).
"""

from __future__ import annotations

from collections.abc import Callable
from uuid import UUID

import psycopg

from aether_policy.domain.decision import Decision


class PostgresPermissionTable:
    def __init__(self, connect: Callable[[], psycopg.Connection]) -> None:
        self._connect = connect

    def lookup(self, agent_version_id: UUID, server_name: str, tool_name: str) -> Decision | None:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT decision FROM control.tool_permissions
                WHERE agent_version_id = %s AND server_name = %s AND tool_name = %s
                """,
                (agent_version_id, server_name, tool_name),
            )
            row = cur.fetchone()
        if row is None:
            return None
        decision: Decision = row[0]
        return decision
