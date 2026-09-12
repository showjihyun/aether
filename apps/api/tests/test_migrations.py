"""spec 0001 R-8: 초기화 스크립트 없는 빈 DB(testcontainers)에서 마이그레이션 왕복.
spec 0002 2.10: 마이그레이션 0002 가 더하는 열·기본값(P1-2a).

역할은 `db_roles`(conftest) 가 이미 만들어 둔 상태 위에서, `upgrade head` →
`downgrade base` → `upgrade head` 가 예외 없이 끝나고 `control`·`data` 스키마와
다섯 테이블이 실재하는지만 봅니다. 열·제약의 세부는 다른 테스트 파일이 봅니다.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Callable

import psycopg
import pytest
from alembic import command
from alembic.config import Config

pytestmark = pytest.mark.integration

_EXPECTED_TABLES = {
    ("control", "agents"),
    ("control", "agent_versions"),
    ("control", "api_keys"),
    ("control", "runs"),
    ("data", "run_executions"),
}


def test_upgrade_downgrade_upgrade_round_trip_recreates_expected_tables(
    alembic_config: Config,
    admin_connection_factory: Callable[[], psycopg.Connection],
) -> None:
    command.upgrade(alembic_config, "head")
    command.downgrade(alembic_config, "base")
    command.upgrade(alembic_config, "head")

    conn = admin_connection_factory()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT table_schema, table_name
                FROM information_schema.tables
                WHERE table_schema IN ('control', 'data')
                """
            )
            found = {(schema, name) for schema, name in cur.fetchall()}
    finally:
        conn.close()

    assert _EXPECTED_TABLES <= found


def test_control_agents_current_version_defaults_to_one(
    admin_connection_factory: Callable[[], psycopg.Connection],
) -> None:
    """spec 0002 2.10: `control.agents.current_version` 은 값을 주지 않아도 `1`."""
    conn = admin_connection_factory()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO control.agents (name) VALUES (%s) RETURNING current_version",
                (f"agent-{uuid.uuid4()}",),
            )
            row = cur.fetchone()
            assert row is not None
            assert row[0] == 1
        conn.commit()
    finally:
        conn.close()


def test_control_runs_has_new_columns_and_status_defaults_to_queued(
    admin_connection_factory: Callable[[], psycopg.Connection],
) -> None:
    """spec 0002 2.10: `control.runs` 투영·선언 열이 존재하고 `status` 기본값은 `queued`."""
    conn = admin_connection_factory()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT column_name FROM information_schema.columns
                WHERE table_schema = 'control' AND table_name = 'runs'
                """
            )
            columns = {row[0] for row in cur.fetchall()}
        expected_columns = {
            "input",
            "status",
            "status_seq",
            "started_at",
            "finished_at",
            "failure_reason",
            "trace_id",
            "cancel_requested_at",
        }
        assert expected_columns <= columns

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
            agent_version_id = row[0]

            cur.execute(
                """
                INSERT INTO control.runs (agent_version_id, input)
                VALUES (%s, %s)
                RETURNING status
                """,
                (agent_version_id, "hello"),
            )
            row = cur.fetchone()
            assert row is not None
            assert row[0] == "queued"
        conn.commit()
    finally:
        conn.close()


def test_data_run_executions_has_lease_columns(
    admin_connection_factory: Callable[[], psycopg.Connection],
) -> None:
    """spec 0002 2.10: `data.run_executions` 에 `lease_owner`·`lease_until` 열."""
    conn = admin_connection_factory()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT column_name FROM information_schema.columns
                WHERE table_schema = 'data' AND table_name = 'run_executions'
                """
            )
            columns = {row[0] for row in cur.fetchall()}
    finally:
        conn.close()

    assert {"lease_owner", "lease_until"} <= columns
