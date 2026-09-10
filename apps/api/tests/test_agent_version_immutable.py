"""spec R-8: `control.agent_versions` 는 BEFORE UPDATE OR DELETE 트리거로 불변.

**관리자 역할**(권한이 전부 있는 역할)로 UPDATE·DELETE 를 시도해 거부되는지 봅니다.
권한 부족으로 막힌 것은 증명이 아니므로(spec R-8) 반드시 권한이 있는 역할을 씁니다.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Callable

import psycopg
import pytest

pytestmark = pytest.mark.integration


def _insert_agent_and_version(conn: psycopg.Connection) -> uuid.UUID:
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
            VALUES (%s, %s, %s)
            RETURNING id
            """,
            (agent_id, 1, json.dumps({"schema_version": 1})),
        )
        row = cur.fetchone()
        assert row is not None
        version_id: uuid.UUID = row[0]
    conn.commit()
    return version_id


def test_update_on_agent_version_is_rejected_by_trigger_not_by_permissions(
    admin_connection_factory: Callable[[], psycopg.Connection],
) -> None:
    conn = admin_connection_factory()
    try:
        version_id = _insert_agent_and_version(conn)

        with pytest.raises(psycopg.errors.RaiseException) as excinfo:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE control.agent_versions SET definition = %s WHERE id = %s",
                    (json.dumps({"schema_version": 2}), version_id),
                )
        conn.rollback()
    finally:
        conn.close()

    assert "immutable" in str(excinfo.value).lower()


def test_delete_on_agent_version_is_rejected_by_trigger_not_by_permissions(
    admin_connection_factory: Callable[[], psycopg.Connection],
) -> None:
    conn = admin_connection_factory()
    try:
        version_id = _insert_agent_and_version(conn)

        with pytest.raises(psycopg.errors.RaiseException) as excinfo:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM control.agent_versions WHERE id = %s", (version_id,))
        conn.rollback()
    finally:
        conn.close()

    assert "immutable" in str(excinfo.value).lower()
