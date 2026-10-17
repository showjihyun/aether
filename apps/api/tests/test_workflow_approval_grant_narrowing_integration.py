"""spec 0005 2.6 개정 5, C-4 (마이그레이션 0011): `aether_data` 의 `control.workflow_approvals`
SELECT 를
**열 단위** 로 좁힙니다 -- 실제 PostgreSQL.

`api-integration`. 증명하는 것:

1. 0011 up -> down -> up 왕복. 되돌리면 0008 의 표 단위 SELECT 로, 올리면 열 단위로 돌아온다.
2. `aether_data` 는 허용된 세 열(`workflow_run_id`, `node_execution_id`,
   `approved_at`)을 SELECT 할 수 있다.
3. `approved_by`·`note` 는 permission denied -- 단독으로도, `SELECT *` 로도, WHERE 절에서도.
4. INSERT·UPDATE·DELETE 는 여전히 불가(0008 회귀), 어느 열에도 쓰기 권한이 없다.
5. `aether_control` 은 영향이 없다(표 단위로 전부 그대로).
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
_TABLE = "control.workflow_approvals"
_ALLOWED = ("workflow_run_id", "node_execution_id", "approved_at")
_DENIED = ("approved_by", "note")
_ALL_COLUMNS = ("id", "workflow_run_id", "node_execution_id", "approved_by", "approved_at", "note")


def _column_privilege(conn: psycopg.Connection, role: str, column: str, privilege: str) -> bool:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT has_column_privilege(%s, %s, %s, %s)", (role, _TABLE, column, privilege)
        )
        row = cur.fetchone()
    assert row is not None
    return bool(row[0])


def _table_privilege(conn: psycopg.Connection, role: str, privilege: str) -> bool:
    with conn.cursor() as cur:
        cur.execute("SELECT has_table_privilege(%s, %s, %s)", (role, _TABLE, privilege))
        row = cur.fetchone()
    assert row is not None
    return bool(row[0])


def _seed_approval(
    admin_connection_factory: _Factory, control_connection_factory: _Factory
) -> tuple[uuid.UUID, uuid.UUID]:
    admin = admin_connection_factory()
    try:
        with admin.cursor() as cur:
            cur.execute(
                "INSERT INTO control.workflows (name) VALUES (%s) RETURNING id",
                (f"wf-{uuid.uuid4()}",),
            )
            wf = cur.fetchone()
            assert wf is not None
            cur.execute(
                "INSERT INTO control.workflow_versions (workflow_id, version, nodes, edges) "
                "VALUES (%s, 1, '[]', '[]') RETURNING id",
                (wf[0],),
            )
            ver = cur.fetchone()
            assert ver is not None
            cur.execute(
                "INSERT INTO control.workflow_runs (workflow_version_id) VALUES (%s) RETURNING id",
                (ver[0],),
            )
            run = cur.fetchone()
            assert run is not None
            run_id: uuid.UUID = run[0]
        admin.commit()
    finally:
        admin.close()
    node_execution_id = uuid.uuid4()
    control = control_connection_factory()
    try:
        with control.cursor() as cur:
            cur.execute(
                "INSERT INTO control.workflow_approvals "
                "(workflow_run_id, node_execution_id, approved_by, note) "
                "VALUES (%s, %s, 'tester', 'a note')",
                (run_id, node_execution_id),
            )
        control.commit()
    finally:
        control.close()
    return run_id, node_execution_id


def test_0011_downgrade_then_upgrade_round_trip(
    alembic_config: Config, admin_connection_factory: _Factory
) -> None:
    """0011 up -> down -> up. 되돌리면 0008 의 표 단위 SELECT, 올리면 열 단위 SELECT 만."""
    command.upgrade(alembic_config, "head")
    command.downgrade(alembic_config, "0010")
    conn = admin_connection_factory()
    try:
        assert _table_privilege(conn, "aether_data", "SELECT")
        for column in _DENIED:
            assert _column_privilege(conn, "aether_data", column, "SELECT")
    finally:
        conn.close()

    command.upgrade(alembic_config, "head")
    conn = admin_connection_factory()
    try:
        assert not _table_privilege(conn, "aether_data", "SELECT")
        for column in _ALLOWED:
            assert _column_privilege(conn, "aether_data", column, "SELECT")
        for column in _DENIED:
            assert not _column_privilege(conn, "aether_data", column, "SELECT")
    finally:
        conn.close()


def test_data_role_can_select_exactly_the_allowed_columns(
    admin_connection_factory: _Factory,
    control_connection_factory: _Factory,
    data_connection_factory: _Factory,
) -> None:
    """C-4: 실행기가 읽는 세 열은 읽힌다."""
    run_id, node_execution_id = _seed_approval(admin_connection_factory, control_connection_factory)
    conn = data_connection_factory()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT workflow_run_id, node_execution_id, approved_at "
                "FROM control.workflow_approvals WHERE node_execution_id = %s",
                (node_execution_id,),
            )
            row = cur.fetchone()
        assert row is not None
        assert row[0] == run_id
        assert row[1] == node_execution_id
        conn.commit()
    finally:
        conn.close()


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT approved_by FROM control.workflow_approvals",
        "SELECT note FROM control.workflow_approvals",
        "SELECT * FROM control.workflow_approvals",
        "SELECT node_execution_id FROM control.workflow_approvals WHERE approved_by = 'tester'",
        "SELECT count(approved_by) FROM control.workflow_approvals",
    ],
)
def test_data_role_can_not_read_the_approver_or_the_note(
    sql: str,
    admin_connection_factory: _Factory,
    control_connection_factory: _Factory,
    data_connection_factory: _Factory,
) -> None:
    """C-4: 승인 주체와 메모는 permission denied. `SELECT *` 와 WHERE 절 참조도 거부된다."""
    _seed_approval(admin_connection_factory, control_connection_factory)
    conn = data_connection_factory()
    try:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            with conn.cursor() as cur:
                cur.execute(sql)
        conn.rollback()
    finally:
        conn.close()


def test_data_role_still_can_not_write(
    admin_connection_factory: _Factory,
    control_connection_factory: _Factory,
    data_connection_factory: _Factory,
) -> None:
    """0008 회귀: INSERT·UPDATE·DELETE 불가."""
    run_id, node_execution_id = _seed_approval(admin_connection_factory, control_connection_factory)
    conn = data_connection_factory()
    try:
        writes = (
            (
                "INSERT INTO control.workflow_approvals "
                "(workflow_run_id, node_execution_id, approved_by) VALUES (%s, %s, 'forged')",
                (run_id, uuid.uuid4()),
            ),
            (
                "UPDATE control.workflow_approvals SET approved_at = now() "
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


def test_catalog_shows_select_on_three_columns_and_nothing_else(
    admin_connection_factory: _Factory,
) -> None:
    """카탈로그: `aether_data` 는 표 단위 권한이 없고, 열 단위로는 세 열의 SELECT 뿐이다."""
    conn = admin_connection_factory()
    try:
        for privilege in ("SELECT", "INSERT", "UPDATE", "DELETE", "TRUNCATE", "REFERENCES"):
            assert not _table_privilege(conn, "aether_data", privilege), privilege
        for column in _ALL_COLUMNS:
            for privilege in ("INSERT", "UPDATE", "REFERENCES"):
                assert not _column_privilege(conn, "aether_data", column, privilege), (
                    column,
                    privilege,
                )
            expected = column in _ALLOWED
            assert _column_privilege(conn, "aether_data", column, "SELECT") is expected, column
        with conn.cursor() as cur:
            cur.execute(
                "SELECT column_name FROM information_schema.column_privileges "
                "WHERE grantee = 'aether_data' AND table_schema = 'control' "
                "AND table_name = 'workflow_approvals' AND privilege_type = 'SELECT' "
                "ORDER BY column_name"
            )
            assert [r[0] for r in cur.fetchall()] == sorted(_ALLOWED)
    finally:
        conn.close()


def test_control_role_is_unaffected(
    admin_connection_factory: _Factory,
    control_connection_factory: _Factory,
) -> None:
    """`aether_control` 은 표 단위 권한 그대로 -- 모든 열을 읽고 쓴다."""
    _seed_approval(admin_connection_factory, control_connection_factory)
    admin = admin_connection_factory()
    try:
        for privilege in ("SELECT", "INSERT"):
            assert _table_privilege(admin, "aether_control", privilege), privilege
    finally:
        admin.close()
    conn = control_connection_factory()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT approved_by, note FROM control.workflow_approvals LIMIT 1")
            assert cur.fetchone() is not None
        conn.commit()
    finally:
        conn.close()
