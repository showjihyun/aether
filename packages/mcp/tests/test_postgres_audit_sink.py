"""spec 0003 2.7, D-9, D-15, C-7: `PostgresAuditSink` 가 `data.tool_call_audit` 에 기록하고,
`aether_control` 로는 그 표에 접근할 수 없으며(P0-8 역할 분리 불변), `aether_data` 는
`control.tool_permissions` 를 SELECT 만 하고 쓰기는 거부됩니다(D-15, C-7).

이 테스트는 마이그레이션 0003 이 만든 표·GRANT 를 전제하므로 `integration` 입니다 —
testcontainers 로 빈 DB 를 관리자 역할로 `head` 까지 올린 뒤 판정합니다
(`tests/support/pg.py`).
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Callable
from datetime import UTC, datetime

import psycopg
import pytest
from aether_mcp.adapters.outbound.audit_sink.postgres import PostgresAuditSink
from aether_mcp.domain.audit import AuditRecord

pytestmark = pytest.mark.integration


def _insert_agent_version_and_run(conn: psycopg.Connection) -> tuple[uuid.UUID, uuid.UUID]:
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
        version_id: uuid.UUID = row[0]

        cur.execute(
            "INSERT INTO control.runs (agent_version_id, input) VALUES (%s, %s) RETURNING id",
            (version_id, "hello"),
        )
        row = cur.fetchone()
        assert row is not None
        run_id: uuid.UUID = row[0]
    conn.commit()
    return version_id, run_id


def test_postgres_audit_sink_inserts_one_row_per_call(
    admin_connection_factory: Callable[[], psycopg.Connection],
    data_connection_factory: Callable[[], psycopg.Connection],
) -> None:
    admin_conn = admin_connection_factory()
    try:
        version_id, run_id = _insert_agent_version_and_run(admin_conn)
    finally:
        admin_conn.close()

    sink = PostgresAuditSink(connect=data_connection_factory)
    record = AuditRecord(
        run_id=run_id,
        agent_version_id=version_id,
        server_name="echo",
        tool_name="echo",
        decision="allow",
        outcome="ok",
        result_bytes=12,
        error_kind=None,
        started_at=datetime.now(UTC),
        duration_ms=5,
    )

    sink.record(record)

    conn = admin_connection_factory()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT run_id, decision, outcome, result_bytes FROM data.tool_call_audit "
                "WHERE run_id = %s",
                (run_id,),
            )
            rows = cur.fetchall()
    finally:
        conn.close()

    assert len(rows) == 1
    assert rows[0][0] == run_id
    assert rows[0][1] == "allow"
    assert rows[0][2] == "ok"
    assert rows[0][3] == 12


def test_control_role_cannot_select_data_tool_call_audit(
    control_connection_factory: Callable[[], psycopg.Connection],
) -> None:
    """spec 2.7: `aether_control` 은 새 데이터 표에도 여전히 아무 권한이 없습니다."""
    conn = control_connection_factory()
    try:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM data.tool_call_audit")
        conn.rollback()
    finally:
        conn.close()


def test_data_role_can_select_but_not_write_control_tool_permissions(
    admin_connection_factory: Callable[[], psycopg.Connection],
    data_connection_factory: Callable[[], psycopg.Connection],
) -> None:
    """spec D-15, C-7: `aether_data` 는 `control.tool_permissions` 를 SELECT 만."""
    admin_conn = admin_connection_factory()
    try:
        version_id, _run_id = _insert_agent_version_and_run(admin_conn)
        with admin_conn.cursor() as cur:
            cur.execute(
                "INSERT INTO control.tool_permissions (agent_version_id, tool_name, decision) "
                "VALUES (%s, %s, %s)",
                (version_id, "echo", "allow"),
            )
        admin_conn.commit()
    finally:
        admin_conn.close()

    data_conn = data_connection_factory()
    try:
        with data_conn.cursor() as cur:
            cur.execute(
                "SELECT decision FROM control.tool_permissions WHERE agent_version_id = %s",
                (version_id,),
            )
            row = cur.fetchone()
            assert row is not None
            assert row[0] == "allow"
        data_conn.rollback()

        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            with data_conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO control.tool_permissions (agent_version_id, tool_name, decision) "
                    "VALUES (%s, %s, %s)",
                    (version_id, "fail", "deny"),
                )
        data_conn.rollback()
    finally:
        data_conn.close()
