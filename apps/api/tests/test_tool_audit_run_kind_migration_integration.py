"""spec 0005 2.8 개정 10, R-14 (P4-5): 마이그레이션 0010 -- `data.tool_call_audit` 의 `run_id` FK 를
풀고 `run_kind` 를 더한다 -- 실제 PostgreSQL.

`api-integration`. 증명하는 것:

1. 0010 up -> down -> up 왕복. 되돌리면 `run_kind` 가 사라지고 FK(`tool_call_audit_run_id_fkey`)가
   돌아오고, 다시 올리면 반대가 된다.
2. 올린 뒤에는 `run_id` 에 FK 가 없고(`NOT NULL` 은 그대로), `run_kind` 는 `agent`/`workflow` 만
   받는다.
3. 0010 이전에 있던 행(Agent Run 의 것)은 `agent` 로 남는다.
4. `aether_data` 가 `run_kind='workflow'` 와 **Workflow Run id**(`control.runs` 에 없는 id)로 INSERT
   할 수 있다.
5. GRANT 변경이 없다(`aether_data` INSERT·SELECT 만, UPDATE·DELETE 없음, `aether_control` 무권한).
6. 되돌리면 `workflow` 행은 **지워진다**(감사 기록을 잃는 downgrade) - `agent` 행은 남는다.
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

_Factory = Callable[[], psycopg.Connection]
_INSERT_AGENT = (
    "INSERT INTO data.tool_call_audit (run_id, agent_version_id, server_name, tool_name, "
    "decision, outcome) VALUES (%s, %s, 'builtin', 'calculator', 'allow', 'ok')"
)


def _insert_with_kind(kind: str) -> str:
    return (
        "INSERT INTO data.tool_call_audit (run_id, agent_version_id, server_name, tool_name, "
        "decision, outcome, run_kind) "
        f"VALUES (%s, %s, 'builtin', 'calculator', 'allow', 'ok', '{kind}')"
    )


def _seed_agent_version(conn: psycopg.Connection) -> uuid.UUID:
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO control.agents (name) VALUES (%s) RETURNING id", (f"a-{uuid.uuid4()}",)
        )
        row = cur.fetchone()
        assert row is not None
        cur.execute(
            "INSERT INTO control.agent_versions (agent_id, version, definition) "
            "VALUES (%s, 1, %s) RETURNING id",
            (row[0], json.dumps({"schema_version": 1})),
        )
        version = cur.fetchone()
        assert version is not None
        version_id: uuid.UUID = version[0]
    conn.commit()
    return version_id


def _seed_agent_run(conn: psycopg.Connection, version_id: uuid.UUID) -> uuid.UUID:
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO control.runs (agent_version_id, input) VALUES (%s, 'x') RETURNING id",
            (version_id,),
        )
        row = cur.fetchone()
        assert row is not None
        run_id: uuid.UUID = row[0]
    conn.commit()
    return run_id


def _fk_names(conn: psycopg.Connection) -> set[str]:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT c.conname FROM pg_constraint c JOIN pg_attribute a "
            "ON a.attrelid = c.conrelid AND a.attnum = ANY (c.conkey) "
            "WHERE c.contype = 'f' AND c.conrelid = 'data.tool_call_audit'::regclass "
            "AND a.attname = 'run_id'"
        )
        return {r[0] for r in cur.fetchall()}


def _has_run_kind(conn: psycopg.Connection) -> bool:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT count(*) FROM information_schema.columns WHERE table_schema = 'data' "
            "AND table_name = 'tool_call_audit' AND column_name = 'run_kind'"
        )
        row = cur.fetchone()
        assert row is not None
        return bool(row[0])


def test_0010_downgrade_then_upgrade_round_trip(
    alembic_config: Config, admin_connection_factory: _Factory
) -> None:
    """0010 up -> down -> up. 되돌리면 FK 가 돌아오고 `run_kind` 가 사라진다. 올리면 반대다."""
    command.upgrade(alembic_config, "head")
    command.downgrade(alembic_config, "0009")

    conn = admin_connection_factory()
    try:
        assert _fk_names(conn) == {"tool_call_audit_run_id_fkey"}
        assert not _has_run_kind(conn)
    finally:
        conn.close()

    command.upgrade(alembic_config, "head")

    conn = admin_connection_factory()
    try:
        assert _fk_names(conn) == set()
        assert _has_run_kind(conn)
    finally:
        conn.close()


def test_run_id_has_no_fk_but_stays_not_null_and_run_kind_is_checked(
    admin_connection_factory: _Factory,
) -> None:
    """FK 가 사라졌고 `run_id` 는 `NOT NULL` 그대로이며 `run_kind` 는 두 값만 받는다."""
    conn = admin_connection_factory()
    try:
        version_id = _seed_agent_version(conn)
        assert _fk_names(conn) == set()
        with conn.cursor() as cur:
            cur.execute(
                "SELECT column_name, is_nullable, column_default "
                "FROM information_schema.columns "
                "WHERE table_schema = 'data' AND table_name = 'tool_call_audit' "
                "AND column_name IN ('run_id', 'run_kind') ORDER BY column_name"
            )
            run_id_col, run_kind_col = cur.fetchall()
            assert run_id_col[1] == "NO"
            assert run_kind_col[1] == "NO"
            assert "'agent'" in run_kind_col[2]
        with pytest.raises(psycopg.errors.CheckViolation):
            with conn.cursor() as cur:
                cur.execute(_insert_with_kind("robot"), (uuid.uuid4(), version_id))
        conn.rollback()
        with pytest.raises(psycopg.errors.NotNullViolation):
            with conn.cursor() as cur:
                cur.execute(_INSERT_AGENT, (None, version_id))
        conn.rollback()
    finally:
        conn.close()


def test_rows_written_before_0010_stay_agent_rows(
    alembic_config: Config, admin_connection_factory: _Factory
) -> None:
    """0010 이전의 행은 전부 Agent Run 의 것이다 - 올리면 기본값 `agent` 가 된다."""
    command.upgrade(alembic_config, "head")
    command.downgrade(alembic_config, "0009")
    conn = admin_connection_factory()
    try:
        version_id = _seed_agent_version(conn)
        run_id = _seed_agent_run(conn, version_id)
        with conn.cursor() as cur:
            cur.execute(_INSERT_AGENT, (run_id, version_id))
        conn.commit()
    finally:
        conn.close()

    command.upgrade(alembic_config, "head")

    conn = admin_connection_factory()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT run_kind FROM data.tool_call_audit WHERE run_id = %s", (run_id,))
            assert cur.fetchall() == [("agent",)]
    finally:
        conn.close()


def test_the_data_role_can_insert_a_workflow_row_with_a_workflow_run_id(
    admin_connection_factory: _Factory, data_connection_factory: _Factory
) -> None:
    """`aether_data` 가 `run_kind='workflow'` 와 `control.runs` 에 없는 id(= Workflow Run id)로
    INSERT 할 수 있다 - 0003 의 FK 가 있었다면 `ForeignKeyViolation` 이었다."""
    admin = admin_connection_factory()
    try:
        version_id = _seed_agent_version(admin)
    finally:
        admin.close()
    workflow_run_id = uuid.uuid4()

    conn = data_connection_factory()
    try:
        with conn.cursor() as cur:
            cur.execute(
                _insert_with_kind("workflow") + " RETURNING run_kind",
                (workflow_run_id, version_id),
            )
            assert cur.fetchone() == ("workflow",)
        conn.commit()
    finally:
        conn.close()


def test_0010_changes_no_grant(admin_connection_factory: _Factory) -> None:
    """GRANT 변경 없음: `aether_data` 는 INSERT·SELECT 만(append-only 그대로), `aether_control` 은
    아무 권한이 없다."""
    conn = admin_connection_factory()
    try:
        result = {}
        with conn.cursor() as cur:
            for role in ("aether_data", "aether_control"):
                for privilege in ("SELECT", "INSERT", "UPDATE", "DELETE"):
                    cur.execute(
                        "SELECT has_table_privilege(%s, 'data.tool_call_audit', %s)",
                        (role, privilege),
                    )
                    row = cur.fetchone()
                    assert row is not None
                    result[(role, privilege)] = bool(row[0])
    finally:
        conn.close()
    assert result == {
        ("aether_data", "SELECT"): True,
        ("aether_data", "INSERT"): True,
        ("aether_data", "UPDATE"): False,
        ("aether_data", "DELETE"): False,
        ("aether_control", "SELECT"): False,
        ("aether_control", "INSERT"): False,
        ("aether_control", "UPDATE"): False,
        ("aether_control", "DELETE"): False,
    }


def test_downgrade_deletes_workflow_rows_and_restores_the_fk(
    alembic_config: Config, admin_connection_factory: _Factory
) -> None:
    """되돌리면 `workflow` 행은 **지워진다**(FK 를 복원하려면 `control.runs` 에 없는 id 가 남을 수
    없다 - 감사 기록을 잃는 downgrade). `agent` 행은 남고 FK 는 돌아온다."""
    command.upgrade(alembic_config, "head")
    conn = admin_connection_factory()
    try:
        version_id = _seed_agent_version(conn)
        agent_run_id = _seed_agent_run(conn, version_id)
        workflow_run_id = uuid.uuid4()
        with conn.cursor() as cur:
            cur.execute(_INSERT_AGENT, (agent_run_id, version_id))
            cur.execute(_insert_with_kind("workflow"), (workflow_run_id, version_id))
        conn.commit()
    finally:
        conn.close()

    command.downgrade(alembic_config, "0009")

    conn = admin_connection_factory()
    try:
        assert _fk_names(conn) == {"tool_call_audit_run_id_fkey"}
        with conn.cursor() as cur:
            cur.execute(
                "SELECT run_id FROM data.tool_call_audit WHERE run_id IN (%s, %s)",
                (agent_run_id, workflow_run_id),
            )
            assert cur.fetchall() == [(agent_run_id,)]
    finally:
        conn.close()
    command.upgrade(alembic_config, "head")
