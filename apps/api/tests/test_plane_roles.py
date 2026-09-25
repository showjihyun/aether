"""spec 0001 R-7, 2.8: `control` / `data` 스키마 권한 분리.
spec 0002 2.10: 마이그레이션 0002 가 더하는 `data.run_states` 도 같은 경계를 지킵니다(P1-2a).
spec 0003 2.7, D-15, C-7, P2-2a: 마이그레이션 0003 이 더하는 `data.tool_call_audit` 과
`control.tool_permissions` 도 같은 경계를 지킵니다. **`control.tool_permissions` 는
새로운 경계입니다** — `aether_data` 가 `control` 스키마에서 SELECT 할 수 있는 표가
셋(`agent_versions`, `runs`, `tool_permissions`)으로 늘고, 그 확대는 SELECT 에서
멈춥니다(INSERT/UPDATE/DELETE 는 여전히 `aether_control` 만).

- `aether_control` 은 `data` 스키마에 아무 권한이 없습니다(USAGE 도 없음) — 새 테이블
  `data.tool_call_audit` 도 예외가 아닙니다.
- `aether_data` 는 `control.agent_versions`·`control.runs`·`control.tool_permissions` 를
  SELECT 만 할 수 있고 INSERT 는 거부됩니다.
- `aether_data` 는 `data.run_executions`·`data.run_states`·`data.tool_call_audit` 에 쓸 수
  있습니다(Data Plane 이 실행합니다).
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
            """
            INSERT INTO control.runs (agent_version_id, input)
            VALUES (%s, %s)
            RETURNING id
            """,
            (agent_version_id, "test-input"),
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


def test_control_role_cannot_select_data_run_states(
    control_connection_factory: Callable[[], psycopg.Connection],
) -> None:
    """spec 0002 2.10: 새 테이블도 `aether_control` 에는 스키마 단계에서 거부됩니다."""
    conn = control_connection_factory()
    try:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM data.run_states")
        conn.rollback()
    finally:
        conn.close()


def test_data_role_can_insert_run_states_for_an_admin_declared_run(
    admin_connection_factory: Callable[[], psycopg.Connection],
    data_connection_factory: Callable[[], psycopg.Connection],
) -> None:
    """spec 0002 2.10: `aether_data` 는 `data.run_states` 에 씁니다(Data Plane 이 상태 영속)."""
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
                "INSERT INTO data.run_states (run_id, state) VALUES (%s, %s)",
                (run_id, json.dumps({"step": 0})),
            )
        data_conn.commit()
    finally:
        data_conn.close()


def test_control_role_cannot_select_data_tool_call_audit(
    control_connection_factory: Callable[[], psycopg.Connection],
) -> None:
    """spec 0003 2.7: 새 데이터 표에도 `aether_control` 은 여전히 아무 권한이 없습니다."""
    conn = control_connection_factory()
    try:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM data.tool_call_audit")
        conn.rollback()
    finally:
        conn.close()


def test_data_role_can_insert_tool_call_audit_for_an_admin_declared_run(
    admin_connection_factory: Callable[[], psycopg.Connection],
    data_connection_factory: Callable[[], psycopg.Connection],
) -> None:
    """spec 0003 2.7, D-9: `aether_data` 는 `data.tool_call_audit` 에 씁니다(호출의 실행 부산물)."""
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
                """
                INSERT INTO data.tool_call_audit (
                    run_id, agent_version_id, server_name, tool_name, decision, outcome
                )
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (run_id, version_id, "echo", "echo", "allow", "ok"),
            )
        data_conn.commit()
    finally:
        data_conn.close()


def test_data_role_cannot_update_or_delete_tool_call_audit(
    admin_connection_factory: Callable[[], psycopg.Connection],
    data_connection_factory: Callable[[], psycopg.Connection],
) -> None:
    """P2-2a 리뷰: `data.tool_call_audit` 는 append-only 입니다(P0-8 `agent_versions`
    불변 트리거와 같은 성질 — 감사 기록은 사후 추적이 목적이므로 기록 주체도 자기
    기록을 고치거나 지울 수 없습니다). `aether_data` 는 INSERT·SELECT 만 되고
    UPDATE·DELETE 는 거부됩니다.
    """
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
                """
                INSERT INTO data.tool_call_audit (
                    run_id, agent_version_id, server_name, tool_name, decision, outcome
                )
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (run_id, version_id, "echo", "echo", "allow", "ok"),
            )
        data_conn.commit()

        with data_conn.cursor() as cur:
            cur.execute(
                "SELECT id FROM data.tool_call_audit WHERE run_id = %s",
                (run_id,),
            )
            row = cur.fetchone()
            assert row is not None
        data_conn.rollback()

        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            with data_conn.cursor() as cur:
                cur.execute(
                    "UPDATE data.tool_call_audit SET outcome = 'error' WHERE run_id = %s",
                    (run_id,),
                )
        data_conn.rollback()

        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            with data_conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM data.tool_call_audit WHERE run_id = %s",
                    (run_id,),
                )
        data_conn.rollback()
    finally:
        data_conn.close()


def test_data_role_can_select_but_not_write_control_tool_permissions(
    admin_connection_factory: Callable[[], psycopg.Connection],
    data_connection_factory: Callable[[], psycopg.Connection],
) -> None:
    """spec 0003 D-15, C-7: `control.tool_permissions` 확대는 `aether_data` 에 SELECT 만.

    쓰기(INSERT/UPDATE/DELETE)는 여전히 `aether_control` 만 할 수 있습니다 — 정책 표는
    선언이고, 선언을 쓰는 것은 Control Plane 입니다.
    """
    admin_conn = admin_connection_factory()
    try:
        version_id = _insert_agent_version(admin_conn)
        with admin_conn.cursor() as cur:
            cur.execute(
                "INSERT INTO control.tool_permissions (agent_version_id, tool_name, decision) "
                "VALUES (%s, %s, %s)",
                (version_id, "echo", "allow"),
            )
        admin_conn.commit()
    finally:
        admin_conn.close()

    data_conn = data_connection_factory()
    try:
        with data_conn.cursor() as cur:
            cur.execute(
                "SELECT decision FROM control.tool_permissions WHERE agent_version_id = %s",
                (version_id,),
            )
            row = cur.fetchone()
            assert row is not None
            assert row[0] == "allow"
        data_conn.rollback()

        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            with data_conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO control.tool_permissions (agent_version_id, tool_name, decision) "
                    "VALUES (%s, %s, %s)",
                    (version_id, "fail", "deny"),
                )
        data_conn.rollback()

        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            with data_conn.cursor() as cur:
                cur.execute(
                    "UPDATE control.tool_permissions SET decision = 'deny' "
                    "WHERE agent_version_id = %s",
                    (version_id,),
                )
        data_conn.rollback()
    finally:
        data_conn.close()
