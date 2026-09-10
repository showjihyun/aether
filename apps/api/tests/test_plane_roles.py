"""spec R-7, 2.8: `control` / `data` 스키마 권한 분리.

- `aether_control` 은 `data` 스키마에 아무 권한이 없습니다(USAGE 도 없음).
- `aether_data` 는 `control.agent_versions`·`control.runs` 를 SELECT 만 할 수 있고
  INSERT 는 거부됩니다.
- `aether_data` 는 `data.run_executions` 에 쓸 수 있습니다(Data Plane 이 실행합니다).
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Callable

import psycopg
import pytest

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


def _insert_run(conn: psycopg.Connection, agent_version_id: uuid.UUID) -> uuid.UUID:
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO control.runs (agent_version_id) VALUES (%s) RETURNING id",
            (agent_version_id,),
        )
        row = cur.fetchone()
        assert row is not None
        run_id: uuid.UUID = row[0]
    conn.commit()
    return run_id


def test_control_role_cannot_select_data_run_executions(
    control_connection_factory: Callable[[], psycopg.Connection],
) -> None:
    conn = control_connection_factory()
    try:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM data.run_executions")
        conn.rollback()
    finally:
        conn.close()


def test_data_role_can_select_but_not_insert_control_agent_versions(
    admin_connection_factory: Callable[[], psycopg.Connection],
    data_connection_factory: Callable[[], psycopg.Connection],
) -> None:
    admin_conn = admin_connection_factory()
    try:
        version_id = _insert_agent_version(admin_conn)
        with admin_conn.cursor() as cur:
            cur.execute("SELECT agent_id FROM control.agent_versions WHERE id = %s", (version_id,))
            row = cur.fetchone()
            assert row is not None
            agent_id = row[0]
    finally:
        admin_conn.close()

    data_conn = data_connection_factory()
    try:
        with data_conn.cursor() as cur:
            cur.execute(
                "SELECT id FROM control.agent_versions WHERE id = %s",
                (version_id,),
            )
            assert cur.fetchone() is not None
        data_conn.rollback()

        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            with data_conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO control.agent_versions (agent_id, version, definition)
                    VALUES (%s, %s, %s)
                    """,
                    (agent_id, 2, json.dumps({"schema_version": 1})),
                )
        data_conn.rollback()
    finally:
        data_conn.close()


def test_data_role_can_insert_run_executions_for_an_admin_declared_run(
    admin_connection_factory: Callable[[], psycopg.Connection],
    data_connection_factory: Callable[[], psycopg.Connection],
) -> None:
    admin_conn = admin_connection_factory()
    try:
        version_id = _insert_agent_version(admin_conn)
        run_id = _insert_run(admin_conn, version_id)
    finally:
        admin_conn.close()

    data_conn = data_connection_factory()
    try:
        with data_conn.cursor() as cur:
            cur.execute(
                "INSERT INTO data.run_executions (run_id, status) VALUES (%s, %s)",
                (run_id, "queued"),
            )
        data_conn.commit()
    finally:
        data_conn.close()
