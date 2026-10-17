"""spec 0005 2.6 개정 5, 2.9, R-8, R-12, R-13 (P4-4): 마이그레이션 0008 -- 승인 경로가 요구하는
스키마 변경 넷과 **새 GRANT 한 줄** -- 실제 PostgreSQL.

`api-integration`. 증명하는 것:

1. 0008 up -> down -> up 왕복. 되돌리면 열 둘·unique 제약·GRANT·`waiting_approval` 값이 사라지고,
   다시 올리면 돌아온다.
2. 승인은 **노드 실행당 한 건** -- 같은 `(workflow_run_id, node_execution_id)` 를 두 번 넣으면
   DB 가 거부한다(R-8 의 승인 판). 다른 노드 실행의 승인은 같은 Run 에 들어간다.
3. **이 PR 의 사람 검토 대상(H-1)**: `aether_data` 는 `control.workflow_approvals` 를 **읽을 수 있고
   쓸 수는 없다.** INSERT·UPDATE·DELETE 가 권한 부족으로 거부되고, 읽기 외의 어떤 권한도 없다.
   `control.workflows` 에는 여전히 아무 권한이 없다.
4. `aether_control` 은 `data` 에 여전히 아무 권한이 없다(0001 R-7).
5. 노드 실행 상태 enum 은 다섯 값(`waiting_approval` 추가)이고, Agent Run 의 enum
   (`data.run_execution_status`)은 **그대로**다 -- `waiting` 값이 바뀌지 않았다(R-13 회귀).
"""

from __future__ import annotations

import uuid
from collections.abc import Callable

import psycopg
import pytest
from alembic import command
from alembic.config import Config

pytestmark = pytest.mark.integration

_Factory = Callable[[], psycopg.Connection]
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
_UNIQUE_NAME = "uq_workflow_approvals_run_node_execution"


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


def _unique_constraints(conn: psycopg.Connection, schema: str, table: str) -> set[str]:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT conname FROM pg_constraint WHERE contype = 'u' AND conrelid = %s::regclass",
            (f"{schema}.{table}",),
        )
        return {r[0] for r in cur.fetchall()}


def _has_privilege(conn: psycopg.Connection, role: str, table: str, privilege: str) -> bool:
    with conn.cursor() as cur:
        cur.execute("SELECT has_table_privilege(%s, %s, %s)", (role, table, privilege))
        row = cur.fetchone()
    assert row is not None
    return bool(row[0])


def _has_column_privilege(
    conn: psycopg.Connection, role: str, table: str, column: str, privilege: str
) -> bool:
    with conn.cursor() as cur:
        cur.execute("SELECT has_column_privilege(%s, %s, %s, %s)", (role, table, column, privilege))
        row = cur.fetchone()
    assert row is not None
    return bool(row[0])


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


def _approve(conn: psycopg.Connection, run_id: uuid.UUID, node_execution_id: uuid.UUID) -> None:
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO control.workflow_approvals "
            "(workflow_run_id, node_execution_id, approved_by) VALUES (%s, %s, 'tester')",
            (run_id, node_execution_id),
        )


def test_0008_downgrade_then_upgrade_round_trip(
    alembic_config: Config, admin_connection_factory: _Factory
) -> None:
    """0008 up -> down -> up. 되돌리면 열 둘·unique 제약·`aether_data` 의 SELECT·`waiting_approval`
    값이 사라지고, 다시 올리면 전부 돌아온다."""
    command.upgrade(alembic_config, "head")
    command.downgrade(alembic_config, "0007")

    conn = admin_connection_factory()
    try:
        assert _column(conn, "control", "workflow_runs", "waiting_node_execution_id") is None
        assert _column(conn, "data", "workflow_run_executions", "waiting_node_execution_id") is None
        assert _UNIQUE_NAME not in _unique_constraints(conn, "control", "workflow_approvals")
        assert not _has_privilege(conn, "aether_data", "control.workflow_approvals", "SELECT")
        assert _labels(conn, "data", "workflow_node_execution_status") == (
            "running",
            "waiting_run",
            "succeeded",
            "failed",
        )
    finally:
        conn.close()

    command.upgrade(alembic_config, "head")

    conn = admin_connection_factory()
    try:
        assert _column(conn, "control", "workflow_runs", "waiting_node_execution_id") == (
            "uuid",
            "YES",
        )
        assert _column(conn, "data", "workflow_run_executions", "waiting_node_execution_id") == (
            "uuid",
            "YES",
        )
        assert _UNIQUE_NAME in _unique_constraints(conn, "control", "workflow_approvals")
        # 0011 이 표 단위 SELECT 를 열 단위로 좁혔다 -- head 에서는 실행기가 읽는 열만 SELECT 된다.
        assert _has_column_privilege(
            conn, "aether_data", "control.workflow_approvals", "node_execution_id", "SELECT"
        )
        assert _labels(conn, "data", "workflow_node_execution_status") == _NODE_STATUSES
    finally:
        conn.close()


def test_downgrade_keeps_a_node_that_was_waiting_for_approval_as_a_running_one(
    alembic_config: Config, admin_connection_factory: _Factory
) -> None:
    """되돌릴 때 `waiting_approval` 인 노드 실행 행은 값이 없어지는 타입으로 갈 수 없다 -- 지우지
    않고 `running`(시작만 하고 멈춘 노드)으로 둔다. 데이터를 잃는 downgrade 가 아니다."""
    command.upgrade(alembic_config, "head")
    conn = admin_connection_factory()
    try:
        run_id = _seed_run(conn)
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO data.workflow_node_executions (workflow_run_id, node_id, status) "
                "VALUES (%s, 'gate', 'waiting_approval') RETURNING id",
                (run_id,),
            )
            row = cur.fetchone()
            assert row is not None
            node_execution_id = row[0]
        conn.commit()
    finally:
        conn.close()

    command.downgrade(alembic_config, "0007")
    conn = admin_connection_factory()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT status::text FROM data.workflow_node_executions WHERE id = %s",
                (node_execution_id,),
            )
            assert cur.fetchone() == ("running",)
    finally:
        conn.close()
    command.upgrade(alembic_config, "head")


def test_an_approval_is_one_per_node_execution_enforced_by_the_database(
    admin_connection_factory: _Factory, control_connection_factory: _Factory
) -> None:
    """spec 2.6 개정 5 (2), R-8: 같은 `(workflow_run_id, node_execution_id)` 를 두 번 넣으면 DB 가
    거부한다 -- append-only 트리거와 함께 "승인 기록 1건" 을 DB 가 지킨다. 다른 노드 실행의 승인은
    같은 Run 에 들어간다."""
    admin = admin_connection_factory()
    try:
        run_id = _seed_run(admin)
    finally:
        admin.close()
    node_execution_id = uuid.uuid4()
    conn = control_connection_factory()
    try:
        _approve(conn, run_id, node_execution_id)
        conn.commit()
        with pytest.raises(psycopg.errors.UniqueViolation) as excinfo:
            _approve(conn, run_id, node_execution_id)
        conn.rollback()
        assert _UNIQUE_NAME in str(excinfo.value)

        _approve(conn, run_id, uuid.uuid4())
        conn.commit()
        with conn.cursor() as cur:
            cur.execute(
                "SELECT count(*) FROM control.workflow_approvals WHERE workflow_run_id = %s",
                (run_id,),
            )
            assert cur.fetchone() == (2,)
    finally:
        conn.close()


def test_data_role_can_read_approvals_and_can_not_write_them(
    admin_connection_factory: _Factory,
    control_connection_factory: _Factory,
    data_connection_factory: _Factory,
) -> None:
    """**H-1**: 새 GRANT 는 SELECT 하나다. 실행기는 승인을 저장된 사실로 **읽을** 수 있고, 쓰거나
    고치거나 지울 수 없다 -- 읽기가 승인을 만들어 내는 길이 되지 않는다."""
    admin = admin_connection_factory()
    try:
        run_id = _seed_run(admin)
    finally:
        admin.close()
    node_execution_id = uuid.uuid4()
    control = control_connection_factory()
    try:
        _approve(control, run_id, node_execution_id)
        control.commit()
    finally:
        control.close()

    conn = data_connection_factory()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT node_execution_id, workflow_run_id FROM control.workflow_approvals "
                "WHERE node_execution_id = %s",
                (node_execution_id,),
            )
            assert cur.fetchone() == (node_execution_id, run_id)
        conn.commit()

        writes = (
            (
                "INSERT INTO control.workflow_approvals "
                "(workflow_run_id, node_execution_id, approved_by) VALUES (%s, %s, 'forged')",
                (run_id, uuid.uuid4()),
            ),
            (
                "UPDATE control.workflow_approvals SET approved_by = 'forged' "
                "WHERE node_execution_id = %s",
                (node_execution_id,),
            ),
            (
                "DELETE FROM control.workflow_approvals WHERE node_execution_id = %s",
                (node_execution_id,),
            ),
        )
        for sql, params in writes:
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                with conn.cursor() as cur:
                    cur.execute(sql, params)
            conn.rollback()
    finally:
        conn.close()


def test_the_new_grant_is_select_and_nothing_else(admin_connection_factory: _Factory) -> None:
    """**H-1**: 카탈로그로 본 `aether_data` 의 `control.workflow_approvals` 권한은 SELECT 뿐이다.
    `control.workflows`(이름 표)에는 여전히 아무 권한이 없다."""
    conn = admin_connection_factory()
    try:
        granted = {
            privilege
            for privilege in (
                "SELECT",
                "INSERT",
                "UPDATE",
                "DELETE",
                "TRUNCATE",
                "REFERENCES",
                "TRIGGER",
            )
            if _has_privilege(conn, "aether_data", "control.workflow_approvals", privilege)
        }
        # 0011: 표 단위 권한은 없고 열 단위 SELECT 만 있다(상세는 grant_narrowing 테스트).
        assert granted == set()
        assert _has_column_privilege(
            conn, "aether_data", "control.workflow_approvals", "node_execution_id", "SELECT"
        )
        for privilege in ("SELECT", "INSERT", "UPDATE", "DELETE"):
            assert not _has_privilege(conn, "aether_data", "control.workflows", privilege)
    finally:
        conn.close()


def test_control_role_still_has_no_access_to_the_data_plane(
    control_connection_factory: _Factory,
) -> None:
    """0001 R-7: 새 열이 `data` 에 생겼어도 `aether_control` 은 `data` 에 아무 권한이 없다 -- 그래서
    지목 대상을 `control` 로 투영했다."""
    conn = control_connection_factory()
    try:
        for table in ("data.workflow_node_executions", "data.workflow_run_executions"):
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                with conn.cursor() as cur:
                    cur.execute(f"SELECT waiting_node_execution_id FROM {table}")
            conn.rollback()
    finally:
        conn.close()


def test_node_execution_status_gains_waiting_approval_and_agent_runs_are_untouched(
    admin_connection_factory: _Factory, data_connection_factory: _Factory
) -> None:
    """R-13 회귀: 노드 실행 상태는 다섯 값이고 `aether_data` 가 `waiting_approval` 을 쓴다. Agent
    Run 의 enum(`data.run_execution_status`)은 일곱 값 그대로이고 `waiting` 이 바뀌지 않았다."""
    admin = admin_connection_factory()
    try:
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
                "VALUES (%s, 'gate', 'waiting_approval') RETURNING status::text",
                (run_id,),
            )
            assert cur.fetchone() == ("waiting_approval",)
        conn.commit()
    finally:
        conn.close()


def test_the_pointer_columns_are_plain_uuids_without_foreign_keys(
    admin_connection_factory: _Factory,
) -> None:
    """0007 의 두 열과 같은 근거: 평면을 넘는 포인터라 FK 가 없다. 실행기가 노드 실행 행을 만든
    직후에
    투영이 적용되므로 순서 경쟁이 없어도 FK 는 `control` -> `data` 방향을 거스른다."""
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
                    WHERE c.contype = 'f' AND c.conrelid = %s::regclass
                      AND a.attname = 'waiting_node_execution_id'
                    """,
                    (f"{schema}.{table}",),
                )
                assert cur.fetchone() == (0,), (schema, table)
    finally:
        conn.close()
