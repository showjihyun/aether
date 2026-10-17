"""spec 0005 2.7 개정 7 (5), R-11, D-4 (P4-3 둘째 물결): 마이그레이션 0009 -- `WAIT` 의 파킹이
요구하는
스키마 변경 -- 실제 PostgreSQL.

`api-integration`. 증명하는 것:

1. 0009 up -> down -> up 왕복. 되돌리면 `wake_at` 열 둘과 두 enum 의 `waiting_timer` 값이 사라지고,
   다시 올리면 돌아온다.
2. `control.workflow_run_status` 는 여덟 값, `data.workflow_node_execution_status` 는 여섯 값이고
   잘못된 값은 DB 가 거부한다. Agent Run 의 enum(`data.run_execution_status`)은 그대로다(R-13).
3. `wake_at` 이 들어가고 읽힌다 -- 정본(`data.workflow_run_executions`, `aether_data`)과 투영
   (`control.workflow_runs`, `aether_control`) 양쪽. FK 가 없다.
4. `aether_data` 는 `data` 쪽에 쓸 수 있고 `aether_control` 은 `data` 에 여전히 아무 권한이
없다(0001
   R-7). **GRANT 변경이 없다**: 0008 과 0009 의 권한 행렬이 같다.
5. 되돌릴 때 `waiting_timer` 인 행은 지우지 않고 `running` 으로 둔다(세 표).
"""

from __future__ import annotations

import datetime
import uuid
from collections.abc import Callable

import psycopg
import pytest
from alembic import command
from alembic.config import Config

pytestmark = pytest.mark.integration

_Factory = Callable[[], psycopg.Connection]
_RUN_STATUSES = (
    "queued",
    "running",
    "waiting_run",
    "waiting_approval",
    "waiting_timer",
    "succeeded",
    "failed",
    "cancelled",
)
_NODE_STATUSES = (
    "running",
    "waiting_run",
    "waiting_approval",
    "waiting_timer",
    "succeeded",
    "failed",
)
_AGENT_RUN_STATUSES = (
    "queued",
    "running",
    "waiting",
    "succeeded",
    "failed",
    "cancelled",
    "timed_out",
)
_WAKE = datetime.datetime(2099, 1, 1, tzinfo=datetime.UTC)  # 먼 미래: 스위퍼가 줍지 않는다
_PRIVILEGES = ("SELECT", "INSERT", "UPDATE", "DELETE", "TRUNCATE", "REFERENCES", "TRIGGER")
_TABLES = (
    "control.workflow_runs",
    "data.workflow_run_executions",
    "data.workflow_node_executions",
    "control.workflow_approvals",
)


def _labels(conn: psycopg.Connection, schema: str, type_name: str) -> tuple[str, ...]:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT e.enumlabel FROM pg_enum e JOIN pg_type t ON t.oid = e.enumtypid "
            "JOIN pg_namespace n ON n.oid = t.typnamespace "
            "WHERE n.nspname = %s AND t.typname = %s ORDER BY e.enumsortorder",
            (schema, type_name),
        )
        return tuple(r[0] for r in cur.fetchall())


def _column(
    conn: psycopg.Connection, schema: str, table: str, column: str
) -> tuple[str, str] | None:
    """`(데이터 타입, is_nullable)` 또는 없으면 `None`."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT data_type, is_nullable FROM information_schema.columns "
            "WHERE table_schema = %s AND table_name = %s AND column_name = %s",
            (schema, table, column),
        )
        row = cur.fetchone()
    return None if row is None else (row[0], row[1])


def _privilege_matrix(conn: psycopg.Connection) -> dict[tuple[str, str, str], bool]:
    matrix: dict[tuple[str, str, str], bool] = {}
    with conn.cursor() as cur:
        for role in ("aether_data", "aether_control"):
            for table in _TABLES:
                for privilege in _PRIVILEGES:
                    cur.execute("SELECT has_table_privilege(%s, %s, %s)", (role, table, privilege))
                    row = cur.fetchone()
                    assert row is not None
                    matrix[(role, table, privilege)] = bool(row[0])
    return matrix


def _seed_run(conn: psycopg.Connection) -> uuid.UUID:
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO control.workflows (name) VALUES (%s) RETURNING id", (f"wf-{uuid.uuid4()}",)
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
            "INSERT INTO control.workflow_runs (workflow_version_id) VALUES (%s) RETURNING id",
            (version[0],),
        )
        run = cur.fetchone()
        assert run is not None
        run_id: uuid.UUID = run[0]
    conn.commit()
    return run_id


def test_0009_downgrade_then_upgrade_round_trip(
    alembic_config: Config, admin_connection_factory: _Factory
) -> None:
    """0009 up -> down -> up. 되돌리면 `wake_at` 열 둘과 두 enum 의 `waiting_timer` 값이 사라지고,
    다시 올리면 전부 돌아온다."""
    command.upgrade(alembic_config, "head")
    command.downgrade(alembic_config, "0008")

    conn = admin_connection_factory()
    try:
        assert _column(conn, "control", "workflow_runs", "wake_at") is None
        assert _column(conn, "data", "workflow_run_executions", "wake_at") is None
        assert "waiting_timer" not in _labels(conn, "control", "workflow_run_status")
        assert "waiting_timer" not in _labels(conn, "data", "workflow_node_execution_status")
        assert _labels(conn, "control", "workflow_run_status") == tuple(
            s for s in _RUN_STATUSES if s != "waiting_timer"
        )
    finally:
        conn.close()

    command.upgrade(alembic_config, "head")

    conn = admin_connection_factory()
    try:
        assert _column(conn, "control", "workflow_runs", "wake_at") == (
            "timestamp with time zone",
            "YES",
        )
        assert _column(conn, "data", "workflow_run_executions", "wake_at") == (
            "timestamp with time zone",
            "YES",
        )
        assert _labels(conn, "control", "workflow_run_status") == _RUN_STATUSES
        assert _labels(conn, "data", "workflow_node_execution_status") == _NODE_STATUSES
    finally:
        conn.close()


def test_both_enums_have_the_value_and_reject_a_wrong_one(
    admin_connection_factory: _Factory, data_connection_factory: _Factory
) -> None:
    """두 enum 에 `waiting_timer` 가 있고 잘못된 값은 DB 가 거부한다. Agent Run 의 enum 은 그대로다
    (R-13 회귀)."""
    admin = admin_connection_factory()
    try:
        assert _labels(admin, "control", "workflow_run_status") == _RUN_STATUSES
        assert _labels(admin, "data", "workflow_node_execution_status") == _NODE_STATUSES
        assert _labels(admin, "data", "run_execution_status") == _AGENT_RUN_STATUSES
        run_id = _seed_run(admin)
    finally:
        admin.close()

    conn = data_connection_factory()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO data.workflow_node_executions (workflow_run_id, node_id, status) "
                "VALUES (%s, 'w', 'waiting_timer') RETURNING status::text",
                (run_id,),
            )
            assert cur.fetchone() == ("waiting_timer",)
        conn.commit()
        for sql in (
            "INSERT INTO data.workflow_node_executions (workflow_run_id, node_id, status) "
            "VALUES (%s, 'bad', 'sleeping')",
            "INSERT INTO data.workflow_run_executions (workflow_run_id, status) "
            "VALUES (%s, 'sleeping')",
        ):
            with pytest.raises(psycopg.errors.InvalidTextRepresentation):
                with conn.cursor() as cur:
                    cur.execute(sql, (run_id,))
            conn.rollback()
    finally:
        conn.close()


def test_wake_at_is_written_and_read_on_the_execution_and_the_projection(
    admin_connection_factory: _Factory,
    data_connection_factory: _Factory,
    control_connection_factory: _Factory,
) -> None:
    """정본(`data.workflow_run_executions`, `aether_data`)과 투영(`control.workflow_runs`,
    `aether_control`) 양쪽에 `wake_at` 이 들어가고 읽힌다 - 상태 `waiting_timer` 와 함께."""
    admin = admin_connection_factory()
    try:
        run_id = _seed_run(admin)
    finally:
        admin.close()

    data = data_connection_factory()
    try:
        with data.cursor() as cur:
            cur.execute(
                "INSERT INTO data.workflow_run_executions (workflow_run_id, status, wake_at) "
                "VALUES (%s, 'waiting_timer', %s)",
                (run_id, _WAKE),
            )
            cur.execute(
                "SELECT status::text, wake_at FROM data.workflow_run_executions "
                "WHERE workflow_run_id = %s",
                (run_id,),
            )
            assert cur.fetchone() == ("waiting_timer", _WAKE)
        data.commit()
    finally:
        data.close()

    control = control_connection_factory()
    try:
        with control.cursor() as cur:
            cur.execute(
                "UPDATE control.workflow_runs SET status = 'waiting_timer', wake_at = %s "
                "WHERE id = %s",
                (_WAKE, run_id),
            )
            cur.execute(
                "SELECT status::text, wake_at FROM control.workflow_runs WHERE id = %s",
                (run_id,),
            )
            assert cur.fetchone() == ("waiting_timer", _WAKE)
        control.commit()
    finally:
        control.close()


def test_the_wake_at_columns_have_no_foreign_keys(admin_connection_factory: _Factory) -> None:
    """`wake_at` 은 시각일 뿐 포인터가 아니다 - 어떤 FK 도 걸려 있지 않다."""
    conn = admin_connection_factory()
    try:
        with conn.cursor() as cur:
            for schema, table in (
                ("control", "workflow_runs"),
                ("data", "workflow_run_executions"),
            ):
                cur.execute(
                    """
                    SELECT count(*) FROM pg_constraint c
                    JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = ANY (c.conkey)
                    WHERE c.contype = 'f' AND c.conrelid = %s::regclass AND a.attname = 'wake_at'
                    """,
                    (f"{schema}.{table}",),
                )
                assert cur.fetchone() == (0,), (schema, table)
    finally:
        conn.close()


def test_control_role_still_has_no_access_to_the_data_plane(
    control_connection_factory: _Factory,
) -> None:
    """0001 R-7: 새 열이 `data` 에 생겼어도 `aether_control` 은 `data` 에 아무 권한이 없다 -- 그래서
    `wake_at` 을 `control` 로 투영했다."""
    conn = control_connection_factory()
    try:
        for table in ("data.workflow_run_executions",):
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                with conn.cursor() as cur:
                    cur.execute(f"SELECT wake_at FROM {table}")
            conn.rollback()
    finally:
        conn.close()


def test_0009_changes_no_grant(alembic_config: Config, admin_connection_factory: _Factory) -> None:
    """GRANT 변경이 없다: 0008 시점과 0009 시점의 두 역할 x 네 표 x 일곱 권한 행렬이 같다."""
    command.upgrade(alembic_config, "head")
    command.downgrade(alembic_config, "0008")
    conn = admin_connection_factory()
    try:
        before = _privilege_matrix(conn)
    finally:
        conn.close()
    # head 가 아니라 0009 까지 -- 0011 이 승인 표의 GRANT 를 의도적으로 좁혔으므로 head 와는 다르다.
    command.upgrade(alembic_config, "0009")
    conn = admin_connection_factory()
    try:
        after = _privilege_matrix(conn)
    finally:
        conn.close()
    command.upgrade(alembic_config, "head")

    assert before == after
    assert before[("aether_data", "data.workflow_run_executions", "UPDATE")] is True
    assert before[("aether_control", "data.workflow_run_executions", "SELECT")] is False


def test_downgrade_keeps_rows_that_were_waiting_for_the_timer_as_running_ones(
    alembic_config: Config, admin_connection_factory: _Factory
) -> None:
    """되돌릴 때 `waiting_timer` 인 행은 값이 없어지는 타입으로 갈 수 없다 -- 지우지 않고 `running`
    으로 둔다(세 표). 데이터를 잃는 downgrade 가 아니다."""
    command.upgrade(alembic_config, "head")
    conn = admin_connection_factory()
    try:
        run_id = _seed_run(conn)
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE control.workflow_runs SET status = 'waiting_timer', wake_at = %s "
                "WHERE id = %s",
                (_WAKE, run_id),
            )
            cur.execute(
                "INSERT INTO data.workflow_run_executions (workflow_run_id, status, wake_at) "
                "VALUES (%s, 'waiting_timer', %s)",
                (run_id, _WAKE),
            )
            cur.execute(
                "INSERT INTO data.workflow_node_executions (workflow_run_id, node_id, status) "
                "VALUES (%s, 'w', 'waiting_timer')",
                (run_id,),
            )
        conn.commit()
    finally:
        conn.close()

    command.downgrade(alembic_config, "0008")
    conn = admin_connection_factory()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT status::text FROM control.workflow_runs WHERE id = %s", (run_id,))
            assert cur.fetchone() == ("running",)
            cur.execute(
                "SELECT status::text FROM data.workflow_run_executions WHERE workflow_run_id = %s",
                (run_id,),
            )
            assert cur.fetchone() == ("running",)
            cur.execute(
                "SELECT status::text FROM data.workflow_node_executions WHERE workflow_run_id = %s",
                (run_id,),
            )
            assert cur.fetchone() == ("running",)
    finally:
        conn.close()
    command.upgrade(alembic_config, "head")
