"""spec 0003 2.1, 2.9, D-5, D-9 (사람 결정 2026-09-27, AR-6 `ignore_imports`):
`aether_worker.main._build_tool_gateway` 가 실제로 조립되는지 — 판정(PostgreSQL) →
호출(실제 stdio 서브프로세스, 저장소 안 builtin 서버) → 감사(PostgreSQL) 전 구간을
실제로 지나 도구 하나를 부릅니다.

`.importlinter` 의 AR-6 예외(`aether_worker.main -> aether_mcp.adapters.outbound.
mcp_client.stdio`)가 이 조립 함수 **하나**에만 열려 있으므로, 이 테스트는 그
예외가 실제로 쓸모 있게 동작하는지(연결이 진짜로 된다는 것)를 증명합니다 — 실제
서브프로세스 + 실제 PostgreSQL 이 필요해 `integration` 입니다.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Callable
from uuid import UUID

import psycopg
import pytest
from aether_worker.main import _build_tool_gateway
from aether_worker.settings import Settings

pytestmark = pytest.mark.integration


def _insert_agent_version_and_run(conn: psycopg.Connection) -> tuple[UUID, UUID]:
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO control.agents (name) VALUES (%s) RETURNING id",
            (f"agent-{uuid.uuid4()}",),
        )
        row = cur.fetchone()
        assert row is not None
        agent_id = row[0]

        cur.execute(
            """
            INSERT INTO control.agent_versions (agent_id, version, definition)
            VALUES (%s, 1, %s)
            RETURNING id
            """,
            (agent_id, json.dumps({"schema_version": 1})),
        )
        row = cur.fetchone()
        assert row is not None
        version_id: UUID = row[0]

        cur.execute(
            "INSERT INTO control.runs (agent_version_id, input) VALUES (%s, %s) RETURNING id",
            (version_id, "manual gateway check"),
        )
        row = cur.fetchone()
        assert row is not None
        run_id: UUID = row[0]
    conn.commit()
    return version_id, run_id


def _insert_allow(conn: psycopg.Connection, version_id: UUID, tool_name: str) -> None:
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO control.tool_permissions "
            "(agent_version_id, server_name, tool_name, decision) VALUES (%s, %s, %s, 'allow')",
            (version_id, "builtin", tool_name),
        )
    conn.commit()


def test_build_tool_gateway_discovers_and_calls_the_builtin_server(
    admin_connection_factory: Callable[[], psycopg.Connection],
    data_connection_factory: Callable[[], psycopg.Connection],
) -> None:
    admin_conn = admin_connection_factory()
    try:
        version_id, run_id = _insert_agent_version_and_run(admin_conn)
        _insert_allow(admin_conn, version_id, "calculator")
    finally:
        admin_conn.close()

    settings = Settings()
    gateway = _build_tool_gateway(settings, data_connection_factory)

    schemas = gateway.discover()
    assert {schema.name for schema in schemas} == {"clock", "calculator"}

    result = gateway.call(run_id, version_id, "calculator", {"expression": "2+2"})

    assert result.content == "4"
    assert result.is_error is False

    conn = admin_connection_factory()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT decision, outcome FROM data.tool_call_audit WHERE run_id = %s", (run_id,)
            )
            rows = cur.fetchall()
    finally:
        conn.close()

    assert rows == [("allow", "ok")]
