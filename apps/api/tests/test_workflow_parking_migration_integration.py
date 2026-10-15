"""spec 0005 2.5 개정 3, 2.9 (P4-2a B2): 마이그레이션 0007 -- `control.workflow_runs.requested_by`
와 `data.workflow_node_executions.status` 를 enum 으로 좁히는 것, 그리고 파킹이 요구하는 FK 둘의
제거 -- 실제 PostgreSQL.

`api-integration`. 증명하는 것:

1. 0007 up -> down -> up 왕복. 되돌리면 열이 사라지고 `status` 는 `text` 로 돌아온다.
2. `status` 는 `data.workflow_node_execution_status`(네 값)이고 `data.run_execution_status`(0001)
   와 **다른 타입**이다. `aether_data` 가 네 값을 쓰고 잘못된 값은 거부된다.
3. `requested_by` 가 들어가고 `control.api_keys` FK 가 걸린다. `aether_data` 의 GRANT 는 넓어지지
   않았다(SELECT 뿐).
4. 파킹 때문에 풀린 FK 둘 -- 자식 Run 의 id 를 api 가 선언하기 **전에** 영속해야 하므로
   (R-8) `agent_run_id`·`waiting_run_id` 는 `control.runs` 를 참조하지 않는다.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable

import psycopg
import pytest
from aether_api.adapters.outbound.db.api_keys import PostgresApiKeyStore
from aether_api.application.usecases.issue_api_key import IssueApiKeyUseCase
from alembic import command
from alembic.config import Config

pytestmark = pytest.mark.integration

_Factory = Callable[[], psycopg.Connection]
_NODE_STATUSES = ("running", "waiting_run", "waiting_approval", "succeeded", "failed")
"""0007 이 만든 네 값 + 0008(P4-4)이 더한 `waiting_approval`. head 기준입니다."""


def _column_type(conn: psycopg.Connection, schema: str, table: str, column: str) -> tuple[str, str]:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT udt_schema, udt_name FROM information_schema.columns "
            "WHERE table_schema = %s AND table_name = %s AND column_name = %s",
            (schema, table, column),
        )
        row = cur.fetchone()
    assert row is not None, (schema, table, column)
    return (row[0], row[1])


def _has_column(conn: psycopg.Connection, schema: str, table: str, column: str) -> bool:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_schema = %s AND table_name = %s AND column_name = %s",
            (schema, table, column),
        )
        return cur.fetchone() is not None


def _foreign_keys_on(conn: psycopg.Connection, schema: str, table: str) -> set[str]:
    """`schema.table` 이 가진 FK 의 `열 -> 참조 표` 집합."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT a.attname, c.confrelid::regclass::text
            FROM pg_constraint c
            JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = ANY (c.conkey)
            WHERE c.contype = 'f' AND c.conrelid = %s::regclass
            """,
            (f"{schema}.{table}",),
        )
        return {f"{r[0]} -> {r[1]}" for r in cur.fetchall()}


def _seed_workflow_run(
    admin: psycopg.Connection, requested_by: uuid.UUID | None = None
) -> uuid.UUID:
    with admin.cursor() as cur:
        cur.execute(
            "INSERT INTO control.workflows (name) VALUES (%s) RETURNING id",
            (f"wf-{uuid.uuid4()}",),
        )
        row = cur.fetchone()
        assert row is not None
        cur.execute(
            "INSERT INTO control.workflow_versions (workflow_id, version, nodes, edges) "
            "VALUES (%s, 1, '[]', '[]') RETURNING id",
            (row[0],),
        )
        version = cur.fetchone()
        assert version is not None
        cur.execute(
            "INSERT INTO control.workflow_runs (workflow_version_id, requested_by) "
            "VALUES (%s, %s) RETURNING id",
            (version[0], requested_by),
        )
        run = cur.fetchone()
        assert run is not None
        run_id: uuid.UUID = run[0]
    admin.commit()
    return run_id


def test_0007_downgrade_then_upgrade_round_trip(
    alembic_config: Config, admin_connection_factory: _Factory
) -> None:
    """spec 0005 2.9: 0007 up -> down -> up. 되돌리면 `requested_by` 가 사라지고 노드 실행의
    `status` 는 `text`, enum 타입은 없다. 다시 올리면 돌아온다."""
    command.upgrade(alembic_config, "head")
    command.downgrade(alembic_config, "0006")

    conn = admin_connection_factory()
    try:
        assert not _has_column(conn, "control", "workflow_runs", "requested_by")
        assert _column_type(conn, "data", "workflow_node_executions", "status") == (
            "pg_catalog",
            "text",
        )
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM pg_type WHERE typname = 'workflow_node_execution_status'")
            assert cur.fetchone() is None
    finally:
        conn.close()

    command.upgrade(alembic_config, "head")

    conn = admin_connection_factory()
    try:
        assert _has_column(conn, "control", "workflow_runs", "requested_by")
        assert _column_type(conn, "data", "workflow_node_executions", "status") == (
            "data",
            "workflow_node_execution_status",
        )
    finally:
        conn.close()


def test_node_execution_status_is_its_own_enum_not_the_agent_run_one(
    admin_connection_factory: _Factory,
) -> None:
    """spec 0005 2.9: 새 enum 은 `data.run_execution_status`(0001, 일곱 값)와 다른 타입이고 값이
    정확히 다섯 개다(0007 의 네 값 + 0008 의 `waiting_approval`)."""
    conn = admin_connection_factory()
    try:
        assert _column_type(conn, "data", "workflow_node_executions", "status") == (
            "data",
            "workflow_node_execution_status",
        )
        with conn.cursor() as cur:
            cur.execute(
                "SELECT e.enumlabel FROM pg_enum e JOIN pg_type t ON t.oid = e.enumtypid "
                "JOIN pg_namespace n ON n.oid = t.typnamespace "
                "WHERE n.nspname = 'data' AND t.typname = 'workflow_node_execution_status' "
                "ORDER BY e.enumsortorder"
            )
            assert tuple(r[0] for r in cur.fetchall()) == _NODE_STATUSES
    finally:
        conn.close()


def test_data_role_writes_the_node_values_and_rejects_the_rest(
    admin_connection_factory: _Factory, data_connection_factory: _Factory
) -> None:
    """spec 0005 2.9: `aether_data` 가 노드 실행의 값을 쓸 수 있고, Agent Run 의 값(`waiting`·
    `queued`)이나 철자가 다른 값은 거부된다."""
    admin = admin_connection_factory()
    try:
        run_id = _seed_workflow_run(admin)
    finally:
        admin.close()
    conn = data_connection_factory()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO data.workflow_node_executions (workflow_run_id, node_id) "
                "VALUES (%s, 'a') RETURNING status::text",
                (run_id,),
            )
            assert cur.fetchone() == ("running",), "기본값은 그대로 running"
            for value in _NODE_STATUSES:
                cur.execute(
                    "UPDATE data.workflow_node_executions SET status = %s "
                    "WHERE workflow_run_id = %s RETURNING status::text",
                    (value, run_id),
                )
                assert cur.fetchone() == (value,)
        conn.commit()
        for bad in ("waiting", "queued", "Running", "cancelled"):
            with pytest.raises(psycopg.errors.InvalidTextRepresentation):
                with conn.cursor() as cur:
                    cur.execute(
                        "UPDATE data.workflow_node_executions SET status = %s "
                        "WHERE workflow_run_id = %s",
                        (bad, run_id),
                    )
            conn.rollback()
    finally:
        conn.close()


def test_requested_by_is_stored_and_references_api_keys(
    control_connection_factory: _Factory, admin_connection_factory: _Factory
) -> None:
    """spec 0005 2.5 개정 3: 자식 Run 이 물려받을 요청자. 실제 api key 는 들어가고 없는 id 는 FK
    위반이며, 비어 있는 값(0007 이전 행)도 허용된다."""
    key_id = IssueApiKeyUseCase(PostgresApiKeyStore(control_connection_factory))(
        f"k-{uuid.uuid4()}"
    ).key.id
    admin = admin_connection_factory()
    try:
        assert "requested_by -> control.api_keys" in _foreign_keys_on(
            admin, "control", "workflow_runs"
        )
        stored = _seed_workflow_run(admin, key_id)
        legacy = _seed_workflow_run(admin, None)
        with admin.cursor() as cur:
            cur.execute(
                "SELECT id, requested_by FROM control.workflow_runs WHERE id IN (%s, %s)",
                (stored, legacy),
            )
            assert dict(cur.fetchall()) == {stored: key_id, legacy: None}
        with pytest.raises(psycopg.errors.ForeignKeyViolation):
            _seed_workflow_run(admin, uuid.uuid4())
        admin.rollback()
    finally:
        admin.close()


def test_data_role_grants_on_workflow_runs_are_not_widened(
    admin_connection_factory: _Factory,
) -> None:
    """spec 0005 2.9 개정 2: 열이 늘었어도 `aether_data` 는 `control.workflow_runs` 에 SELECT
    뿐이다(GRANT 변경 없음)."""
    conn = admin_connection_factory()
    try:
        with conn.cursor() as cur:
            for privilege, expected in (
                ("SELECT", True),
                ("INSERT", False),
                ("UPDATE", False),
                ("DELETE", False),
            ):
                cur.execute(
                    "SELECT has_table_privilege('aether_data', 'control.workflow_runs', %s)",
                    (privilege,),
                )
                assert cur.fetchone() == (expected,), privilege
            cur.execute(
                "SELECT has_column_privilege('aether_data', 'control.workflow_runs', "
                "'requested_by', 'SELECT')"
            )
            assert cur.fetchone() == (True,)
    finally:
        conn.close()


def test_child_run_references_do_not_constrain_ahead_of_the_api_declaration(
    admin_connection_factory: _Factory,
) -> None:
    """spec 0005 2.9, R-8: 실행기는 자식 Run 의 id 를 **영속한 뒤에** 발사하고 api 가 그 id 로
    선언한다 -- 영속 시점에는 `control.runs` 행이 없다. 그래서 `agent_run_id` 와 `waiting_run_id`
    (투영도 같은 경쟁)는 `control.runs` 를 참조하지 않는다. 다른 FK 는 그대로다."""
    conn = admin_connection_factory()
    try:
        node_fks = _foreign_keys_on(conn, "data", "workflow_node_executions")
        run_fks = _foreign_keys_on(conn, "control", "workflow_runs")
        assert node_fks == {"workflow_run_id -> control.workflow_runs"}
        assert run_fks == {
            "workflow_version_id -> control.workflow_versions",
            "requested_by -> control.api_keys",
        }
        run_id = _seed_workflow_run(conn)
        with conn.cursor() as cur:
            ghost = uuid.uuid4()
            cur.execute(
                "INSERT INTO data.workflow_node_executions "
                "(workflow_run_id, node_id, agent_run_id) VALUES (%s, 'a', %s)",
                (run_id, ghost),
            )
            cur.execute(
                "UPDATE control.workflow_runs SET waiting_run_id = %s WHERE id = %s",
                (ghost, run_id),
            )
        conn.commit()
    finally:
        conn.close()
