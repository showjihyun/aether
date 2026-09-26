"""spec 0003 2.7, D-15, 개정 4 (🔒 P2-4): `PostgresPermissionTable` 이
`control.tool_permissions` 을 `aether_data` 역할(SELECT 만)로 읽습니다.

이 테스트는 마이그레이션 0003 이 만든 표·GRANT 를 전제하므로 `integration` 입니다.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Callable

import psycopg
import pytest
from aether_policy.adapters.outbound.permission_table.postgres import PostgresPermissionTable

pytestmark = pytest.mark.integration


def _insert_agent_version(conn: psycopg.Connection) -> uuid.UUID:
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
    conn.commit()
    return version_id


def test_lookup_returns_none_when_no_row_declared(
    admin_connection_factory: Callable[[], psycopg.Connection],
    data_connection_factory: Callable[[], psycopg.Connection],
) -> None:
    admin_conn = admin_connection_factory()
    try:
        version_id = _insert_agent_version(admin_conn)
    finally:
        admin_conn.close()

    table = PostgresPermissionTable(data_connection_factory)

    assert table.lookup(version_id, "filesystem", "read") is None


def test_lookup_returns_the_declared_decision(
    admin_connection_factory: Callable[[], psycopg.Connection],
    data_connection_factory: Callable[[], psycopg.Connection],
) -> None:
    admin_conn = admin_connection_factory()
    try:
        version_id = _insert_agent_version(admin_conn)
        with admin_conn.cursor() as cur:
            cur.execute(
                "INSERT INTO control.tool_permissions "
                "(agent_version_id, server_name, tool_name, decision) "
                "VALUES (%s, %s, %s, %s)",
                (version_id, "filesystem", "read", "allow"),
            )
        admin_conn.commit()
    finally:
        admin_conn.close()

    table = PostgresPermissionTable(data_connection_factory)

    assert table.lookup(version_id, "filesystem", "read") == "allow"


def test_lookup_writing_with_data_role_is_rejected(
    admin_connection_factory: Callable[[], psycopg.Connection],
    data_connection_factory: Callable[[], psycopg.Connection],
) -> None:
    """spec D-15, C-7: `aether_data` 로 정책 표 INSERT 는 여전히 거부됩니다."""
    admin_conn = admin_connection_factory()
    try:
        version_id = _insert_agent_version(admin_conn)
    finally:
        admin_conn.close()

    data_conn = data_connection_factory()
    try:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            with data_conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO control.tool_permissions "
                    "(agent_version_id, server_name, tool_name, decision) "
                    "VALUES (%s, %s, %s, %s)",
                    (version_id, "filesystem", "read", "allow"),
                )
        data_conn.rollback()
    finally:
        data_conn.close()
