"""spec 0007 2.3, D-3, D-4, R-5 (P5-1): 마이그레이션 0012 -- 노드 실행 투영 표
`control.workflow_node_states` 와 그 GRANT -- 실제 PostgreSQL.

`api-integration`. 증명하는 것:

1. 0012 up -> down -> up 왕복.
2. 열은 **화면이 쓰는 것만**이다: 노드 출력(`output`)·입력·자식 Run id 같은 열이 없다(D-4).
3. 키는 `(workflow_run_id, node_id)` 이다 -- 같은 키를 두 번 넣으면 DB 가 거부한다.
4. **구조적 요점(spec 0001 R-7, AR-13)**: `aether_data` 는 이 표에 INSERT·UPDATE·DELETE 도,
   SELECT 도 할 수 없다. 투영의 쓰는 주체는 api(`aether_control`) 하나다.
5. `aether_control` 은 이 표를 쓰고 읽는다. 그리고 `data` 에는 **여전히 권한이 0건**이다.
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
_TABLE = "control.workflow_node_states"
_COLUMNS = (
    "failure_reason",
    "finished_at",
    "kind",
    "node_id",
    "started_at",
    "status",
    "status_seq",
    "workflow_run_id",
)
_PRIVILEGES = ("SELECT", "INSERT", "UPDATE", "DELETE")


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


def _table_exists(conn: psycopg.Connection) -> bool:
    with conn.cursor() as cur:
        cur.execute("SELECT to_regclass(%s)", (_TABLE,))
        row = cur.fetchone()
    assert row is not None
    return row[0] is not None


def _columns(conn: psycopg.Connection) -> tuple[str, ...]:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema = 'control' AND table_name = 'workflow_node_states' "
            "ORDER BY column_name"
        )
        return tuple(r[0] for r in cur.fetchall())


def _has_privilege(conn: psycopg.Connection, role: str, table: str, privilege: str) -> bool:
    with conn.cursor() as cur:
        cur.execute("SELECT has_table_privilege(%s, %s, %s)", (role, table, privilege))
        row = cur.fetchone()
    assert row is not None
    return bool(row[0])


def test_0012_downgrade_then_upgrade_round_trip(
    alembic_config: Config, admin_connection_factory: _Factory
) -> None:
    """0012 up -> down -> up. 되돌리면 표가 사라지고 다시 올리면 돌아온다."""
    command.upgrade(alembic_config, "head")
    command.downgrade(alembic_config, "0011")
    conn = admin_connection_factory()
    try:
        assert not _table_exists(conn)
    finally:
        conn.close()

    command.upgrade(alembic_config, "head")
    conn = admin_connection_factory()
    try:
        assert _table_exists(conn)
    finally:
        conn.close()


def test_the_projection_has_only_the_columns_the_screen_reads(
    admin_connection_factory: _Factory,
) -> None:
    """D-4: 노드 출력·입력·자식 Run id 열이 없다 -- 열 여덟이 전부다."""
    conn = admin_connection_factory()
    try:
        assert _columns(conn) == _COLUMNS
    finally:
        conn.close()


def test_the_key_is_workflow_run_id_and_node_id(
    admin_connection_factory: _Factory, control_connection_factory: _Factory
) -> None:
    """키는 `(workflow_run_id, node_id)` -- 같은 키 두 번은 거부, 다른 node_id 는 허용."""
    admin = admin_connection_factory()
    try:
        run_id = _seed_run(admin)
    finally:
        admin.close()
    conn = control_connection_factory()
    try:
        insert = (
            "INSERT INTO control.workflow_node_states "
            "(workflow_run_id, node_id, kind, status, status_seq) "
            "VALUES (%s, %s, 'AGENT', 'running', 1)"
        )
        with conn.cursor() as cur:
            cur.execute(insert, (run_id, "a"))
            cur.execute(insert, (run_id, "b"))
        conn.commit()
        with pytest.raises(psycopg.errors.UniqueViolation):
            with conn.cursor() as cur:
                cur.execute(insert, (run_id, "a"))
        conn.rollback()
    finally:
        conn.close()


def test_data_role_cannot_write_or_read_the_projection(
    admin_connection_factory: _Factory, data_connection_factory: _Factory
) -> None:
    """spec 0001 R-7, AR-13, D-3: `aether_data` 는 투영 표에 쓸 수 없다 -- 권한이 한 줄도 없다."""
    admin = admin_connection_factory()
    try:
        run_id = _seed_run(admin)
        for privilege in _PRIVILEGES:
            assert not _has_privilege(admin, "aether_data", _TABLE, privilege), privilege
    finally:
        admin.close()
    conn = data_connection_factory()
    try:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO control.workflow_node_states "
                    "(workflow_run_id, node_id, kind, status, status_seq) "
                    "VALUES (%s, 'a', 'AGENT', 'running', 1)",
                    (run_id,),
                )
        conn.rollback()
        for statement in (
            "UPDATE control.workflow_node_states SET status_seq = 9",
            "DELETE FROM control.workflow_node_states",
            "SELECT node_id FROM control.workflow_node_states",
        ):
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                with conn.cursor() as cur:
                    cur.execute(statement)
            conn.rollback()
    finally:
        conn.close()


def test_control_role_owns_the_projection_and_still_has_nothing_in_data(
    admin_connection_factory: _Factory,
) -> None:
    """`aether_control` 은 이 표의 네 권한을 다 갖고, `data` 스키마 표에는 0건이다(0001 R-7)."""
    conn = admin_connection_factory()
    try:
        for privilege in _PRIVILEGES:
            assert _has_privilege(conn, "aether_control", _TABLE, privilege), privilege
        with conn.cursor() as cur:
            cur.execute(
                "SELECT count(*) FROM information_schema.role_table_grants "
                "WHERE grantee = 'aether_control' AND table_schema = 'data'"
            )
            assert cur.fetchone() == (0,)
    finally:
        conn.close()
