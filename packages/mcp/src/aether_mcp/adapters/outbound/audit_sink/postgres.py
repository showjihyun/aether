"""spec 0003 2.7, D-9: `AuditSink` 의 PostgreSQL 구현 — `data.tool_call_audit` 에 INSERT.

`connect` 는 연결 **팩토리**입니다(`packages/runtime` 의 `PostgresRunStateStore` 와
같은 패턴) — 메서드마다 새 연결을 열고 `with connect() as conn:` 이 커밋·롤백·닫기를
맡깁니다(psycopg3 의 `Connection.__exit__`).
"""

from __future__ import annotations

from collections.abc import Callable

import psycopg

from aether_mcp.domain.audit import AuditRecord


class PostgresAuditSink:
    def __init__(self, connect: Callable[[], psycopg.Connection]) -> None:
        self._connect = connect

    def record(self, record: AuditRecord) -> None:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO data.tool_call_audit (
                    run_id, agent_version_id, server_name, tool_name,
                    decision, outcome, result_bytes, error_kind,
                    started_at, duration_ms
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    record.run_id,
                    record.agent_version_id,
                    record.server_name,
                    record.tool_name,
                    record.decision,
                    record.outcome,
                    record.result_bytes,
                    record.error_kind,
                    record.started_at,
                    record.duration_ms,
                ),
            )
