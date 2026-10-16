"""spec 0005 2.2, 2.3, 2.9, D-3, D-5, D-12, R-1, R-2 (P4-1): 마이그레이션 0005 와 Workflow 정의
API — 실제 PostgreSQL.

`api-integration`. 다섯 표의 평면·GRANT 경계, 0005 의 up/down 왕복(0004 의 표와 `vector`
확장에 회귀 없음), Version 불변(DB 트리거와 API 양쪽), 승인 기록 append-only, 새 enum 이
`data.run_execution_status` 를 건드리지 않는 것.
"""

from __future__ import annotations

import json
import threading
import uuid
from collections.abc import Callable
from typing import Any

import psycopg
import pytest
from aether_api.adapters.outbound.db.api_keys import PostgresApiKeyStore
from aether_api.application.usecases.issue_api_key import IssueApiKeyUseCase
from aether_api.main import create_app
from aether_api.settings import Settings
from aether_workflow.domain.condition import ConditionOperator
from aether_workflow.domain.node import Edge, Node, NodeKind
from aether_workflow.domain.serialization import serialize_version
from aether_workflow.domain.workflow_version import WorkflowVersion
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient

pytestmark = pytest.mark.integration

_NEW_TABLES = {
    ("control", "workflows"),
    ("control", "workflow_versions"),
    ("control", "workflow_runs"),
    ("control", "workflow_approvals"),
    ("data", "workflow_node_executions"),
}
_RUN_STATUS_VALUES = [
    "queued",
    "running",
    "waiting_run",
    "waiting_approval",
    "succeeded",
    "failed",
    "cancelled",
]
_Factory = Callable[[], psycopg.Connection]


def _tables(conn: psycopg.Connection) -> set[tuple[str, str]]:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT table_schema, table_name FROM information_schema.tables "
            "WHERE table_schema IN ('control', 'data')"
        )
        return {(s, n) for s, n in cur.fetchall()}


def _enum_labels(conn: psycopg.Connection, schema: str, name: str) -> list[str]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT e.enumlabel FROM pg_enum e
            JOIN pg_type t ON t.oid = e.enumtypid
            JOIN pg_namespace n ON n.oid = t.typnamespace
            WHERE n.nspname = %s AND t.typname = %s
            ORDER BY e.enumsortorder
            """,
            (schema, name),
        )
        return [r[0] for r in cur.fetchall()]


def _seed_workflow_run(conn: psycopg.Connection) -> dict[str, uuid.UUID]:
    """관리자 연결로 workflow → version 1 → run 을 만들고 id 들을 돌려줍니다."""
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO control.workflows (name) VALUES (%s) RETURNING id",
            (f"wf-{uuid.uuid4()}",),
        )
        row = cur.fetchone()
        assert row is not None
        workflow_id = row[0]
        cur.execute(
            "INSERT INTO control.workflow_versions (workflow_id, version, nodes, edges) "
            "VALUES (%s, 1, '[]', '[]') RETURNING id",
            (workflow_id,),
        )
        row = cur.fetchone()
        assert row is not None
        version_id = row[0]
        cur.execute(
            "INSERT INTO control.workflow_runs (workflow_version_id) VALUES (%s) "
            "RETURNING id, status",
            (version_id,),
        )
        row = cur.fetchone()
        assert row is not None
        run_id, status = row
        assert status == "queued"
    conn.commit()
    return {"workflow": workflow_id, "version": version_id, "run": run_id}


# --- 마이그레이션 ---------------------------------------------------------------


def test_0005_downgrade_then_upgrade_round_trip_leaves_0004_intact(
    alembic_config: Config,
    admin_connection_factory: _Factory,
) -> None:
    """spec 0005 2.9: 0005 up/down 왕복. 되돌리면 다섯 표와 새 enum 이 사라지고 0004 의
    표·`vector` 확장은 그대로이며, 다시 올리면 돌아온다."""
    command.upgrade(alembic_config, "head")
    command.downgrade(alembic_config, "0004")

    conn = admin_connection_factory()
    try:
        found = _tables(conn)
        assert not (_NEW_TABLES & found), "downgrade 뒤에도 0005 의 표가 남았다"
        assert _enum_labels(conn, "control", "workflow_run_status") == []
        assert {("control", "knowledge_sets"), ("data", "agent_memory")} <= found
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM pg_extension WHERE extname = 'vector'")
            assert cur.fetchone() is not None, "0005 downgrade 가 vector 확장을 건드렸다"
    finally:
        conn.close()

    command.upgrade(alembic_config, "head")

    conn = admin_connection_factory()
    try:
        assert _NEW_TABLES <= _tables(conn)
    finally:
        conn.close()


def test_workflow_run_status_is_a_new_enum_and_run_execution_status_is_untouched(
    admin_connection_factory: _Factory,
) -> None:
    """spec 0005 2.3: 값 일곱 개(`timed_out` 없음), 별도 타입. 0001 의 enum 은 그대로."""
    conn = admin_connection_factory()
    try:
        assert _enum_labels(conn, "control", "workflow_run_status") == _RUN_STATUS_VALUES
        run_execution = _enum_labels(conn, "data", "run_execution_status")
        assert "timed_out" in run_execution
        assert "waiting_run" not in run_execution
        assert "waiting_approval" not in run_execution
    finally:
        conn.close()


# --- 평면과 GRANT ---------------------------------------------------------------


def test_control_role_cannot_touch_data_workflow_node_executions(
    control_connection_factory: _Factory,
) -> None:
    """spec 0005 2.9, D-5, 0001 R-7: `aether_control` 은 `data` 에 접근하지 못한다."""
    conn = control_connection_factory()
    try:
        for sql in (
            "SELECT * FROM data.workflow_node_executions",
            "INSERT INTO data.workflow_node_executions (workflow_run_id, node_id) "
            f"VALUES ('{uuid.uuid4()}', 'x')",
        ):
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                with conn.cursor() as cur:
                    cur.execute(sql)
            conn.rollback()
    finally:
        conn.close()


def test_data_role_reads_workflow_versions_and_runs_but_cannot_write_them(
    admin_connection_factory: _Factory,
    data_connection_factory: _Factory,
) -> None:
    """spec 0005 2.9: `aether_data` 는 `control.workflow_versions`·`workflow_runs` 를 SELECT
    할 수 있고 INSERT 는 거부된다."""
    admin = admin_connection_factory()
    try:
        ids = _seed_workflow_run(admin)
    finally:
        admin.close()

    conn = data_connection_factory()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM control.workflow_versions WHERE id = %s", (ids["version"],))
            assert cur.fetchone() is not None
            cur.execute("SELECT 1 FROM control.workflow_runs WHERE id = %s", (ids["run"],))
            assert cur.fetchone() is not None
        conn.rollback()

        writes = (
            (
                "INSERT INTO control.workflow_versions (workflow_id, version, nodes, edges) "
                "VALUES (%s, 2, '[]', '[]')",
                (ids["workflow"],),
            ),
            (
                "INSERT INTO control.workflow_runs (workflow_version_id) VALUES (%s)",
                (ids["version"],),
            ),
            ("UPDATE control.workflow_runs SET status = 'running' WHERE id = %s", (ids["run"],)),
        )
        for sql, params in writes:
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                with conn.cursor() as cur:
                    cur.execute(sql, params)
            conn.rollback()
    finally:
        conn.close()


def test_data_role_has_no_access_to_the_workflows_name_table(
    data_connection_factory: _Factory,
) -> None:
    """spec 0005 2.9: 실행기는 이름 표를 읽을 이유가 없어 SELECT 도 주지 않았다. (승인 기록은
    0008(P4-4)이 SELECT 만 더했다 - `test_workflow_approval_migration_integration.py` 가
    읽기 가능·쓰기 불가를 판정한다.)"""
    conn = data_connection_factory()
    try:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM control.workflows")
        conn.rollback()
    finally:
        conn.close()


def test_data_role_writes_node_executions_and_links_the_child_agent_run_on_its_side(
    admin_connection_factory: _Factory,
    data_connection_factory: _Factory,
) -> None:
    """spec 0005 2.9, D-3: 노드 실행 기록은 `aether_data` 가 쓰고, 자식 Agent Run 과의
    연결은 `data.workflow_node_executions.agent_run_id` 에 있다(Run 쪽에 Workflow 참조 없음).
    같은 (run, node, iteration) 은 두 번 기록되지 않는다(재개 멱등의 토대, R-8)."""
    admin = admin_connection_factory()
    try:
        ids = _seed_workflow_run(admin)
        with admin.cursor() as cur:
            cur.execute(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema = 'control' AND table_name = 'runs'"
            )
            run_columns = {r[0] for r in cur.fetchall()}
    finally:
        admin.close()
    assert not any("workflow" in c for c in run_columns), run_columns

    conn = data_connection_factory()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO data.workflow_node_executions (workflow_run_id, node_id, output) "
                "VALUES (%s, 'a', %s) RETURNING status, output_truncated, agent_run_id",
                (ids["run"], json.dumps({"k": "v"})),
            )
            assert cur.fetchone() == ("running", False, None)
        conn.commit()
        with pytest.raises(psycopg.errors.UniqueViolation):
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO data.workflow_node_executions (workflow_run_id, node_id) "
                    "VALUES (%s, 'a')",
                    (ids["run"],),
                )
        conn.rollback()
    finally:
        conn.close()


def test_control_role_can_write_all_four_control_tables(
    control_connection_factory: _Factory,
) -> None:
    """spec 0005 2.9: `aether_control` 은 `control` 의 새 표 넷을 쓴다(승인 기록 포함)."""
    conn = control_connection_factory()
    try:
        ids = _seed_workflow_run(conn)
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO control.workflow_approvals "
                "(workflow_run_id, node_execution_id, approved_by) VALUES (%s, %s, 'tester') "
                "RETURNING approved_at, note",
                (ids["run"], uuid.uuid4()),
            )
            row = cur.fetchone()
            assert row is not None
            assert row[0] is not None and row[1] is None
        conn.commit()
    finally:
        conn.close()


# --- 불변 ------------------------------------------------------------------------


@pytest.mark.parametrize(
    "mutation",
    [
        "UPDATE control.workflow_versions SET nodes = '[1]' WHERE id = %(version)s",
        "DELETE FROM control.workflow_versions WHERE id = %(version)s",
        "UPDATE control.workflow_approvals SET approved_by = 'someone' WHERE id = %(approval)s",
        "DELETE FROM control.workflow_approvals WHERE id = %(approval)s",
    ],
    ids=["version-update", "version-delete", "approval-update", "approval-delete"],
)
def test_versions_are_immutable_and_approvals_are_append_only_by_trigger(
    admin_connection_factory: _Factory, mutation: str
) -> None:
    """spec 0005 D-12, 2.6: **관리자 역할**로도 UPDATE·DELETE 가 트리거에 거부된다(권한 부족으로
    막힌 것은 증명이 아니다, 0001 R-8 과 같은 기준)."""
    conn = admin_connection_factory()
    try:
        ids = _seed_workflow_run(conn)
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO control.workflow_approvals "
                "(workflow_run_id, node_execution_id, approved_by) VALUES (%s, %s, 'tester') "
                "RETURNING id",
                (ids["run"], uuid.uuid4()),
            )
            row = cur.fetchone()
            assert row is not None
            approval_id = row[0]
        conn.commit()

        with pytest.raises(psycopg.errors.RaiseException) as excinfo:
            with conn.cursor() as cur:
                cur.execute(mutation, {"version": ids["version"], "approval": approval_id})
        conn.rollback()
    finally:
        conn.close()
    assert "immutable" in str(excinfo.value).lower()


# --- API ---------------------------------------------------------------------------


@pytest.fixture
def client(control_database_url: str) -> TestClient:
    return TestClient(create_app(Settings(database_url=control_database_url)))


@pytest.fixture
def auth_headers(control_connection_factory: _Factory) -> dict[str, str]:
    store = PostgresApiKeyStore(control_connection_factory)
    issued = IssueApiKeyUseCase(store)(f"test-workflows-api-{uuid.uuid4()}")
    return {"Authorization": f"Bearer {issued.raw_key}"}


_AGENT_ID = "00000000-0000-0000-0000-0000000000a1"


def _n(
    node_id: str,
    kind: str,
    max_iterations: int | None = None,
    agent_id: str | None = None,
    agent_version: int | None = None,
) -> dict[str, Any]:
    """`AGENT` 는 기본으로 Agent 를 가리킵니다(spec 0005 2.2 개정 3 — 아니면 400)."""
    if kind == "AGENT" and agent_id is None:
        agent_id = _AGENT_ID
    return {
        "id": node_id,
        "kind": kind,
        "max_iterations": max_iterations,
        "agent_id": agent_id,
        "agent_version": agent_version,
    }


def _e(source: str, target: str, label: str | None = None) -> dict[str, Any]:
    return {"source": source, "target": target, "label": label}


_V1 = {
    "nodes": [_n("s", "START"), _n("a", "AGENT"), _n("l", "LOOP", 3), _n("e", "END")],
    "edges": [_e("s", "a"), _e("a", "l"), _e("l", "e", "done")],
}
_V2 = {
    "nodes": [_n("s", "START"), _n("b", "LLM"), _n("e", "END")],
    "edges": [_e("s", "b"), _e("b", "e")],
}


def _as_version(number: int, body: dict[str, Any]) -> WorkflowVersion:
    return WorkflowVersion(
        number=number,
        nodes=tuple(
            Node(
                id=n["id"],
                kind=NodeKind(n["kind"]),
                max_iterations=n["max_iterations"],
                agent_id=uuid.UUID(n["agent_id"]) if n["agent_id"] is not None else None,
                agent_version=n["agent_version"],
                condition_path=n.get("condition_path"),
                condition_operator=(
                    ConditionOperator(n["condition_operator"])
                    if n.get("condition_operator") is not None
                    else None
                ),
                condition_value=n.get("condition_value"),
            )
            for n in body["nodes"]
        ),
        edges=tuple(Edge(e["source"], e["target"], e["label"]) for e in body["edges"]),
    )


def test_put_creates_version_two_and_version_one_is_byte_identical(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    """spec 0005 R-2, D-12: PUT 으로 Version 2 를 만들어도 Version 1 의 노드·간선은
    **바이트 단위로 같다**(`serialize_version` 으로 비교)."""
    created = client.post(
        "/workflows", json={"name": f"wf-{uuid.uuid4()}", **_V1}, headers=auth_headers
    )
    assert created.status_code == 201, created.text
    workflow_id = created.json()["id"]

    def v1_bytes() -> bytes:
        body = client.get(f"/workflows/{workflow_id}/versions/1", headers=auth_headers).json()
        assert body["version"] == 1
        return serialize_version(_as_version(1, body))

    before = v1_bytes()
    assert before == serialize_version(_as_version(1, _V1))

    put = client.put(f"/workflows/{workflow_id}", json=_V2, headers=auth_headers)
    assert put.status_code == 200, put.text
    assert put.json()["current_version"] == 2

    assert v1_bytes() == before
    v2 = client.get(f"/workflows/{workflow_id}/versions/2", headers=auth_headers).json()
    assert serialize_version(_as_version(2, v2)) == serialize_version(_as_version(2, _V2))
    current = client.get(f"/workflows/{workflow_id}", headers=auth_headers).json()
    assert current["current_version"] == 2
    assert [n["id"] for n in current["nodes"]] == ["s", "b", "e"]


def test_condition_keys_survive_storage_and_the_stored_version_serializes_identically(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    """spec 0005 2.2 개정 4, R-2: `CONDITION` 의 세 키가 `jsonb` 를 왕복하고(값의 타입 포함), 저장된
    Version 의 직렬화가 요청 본문의 것과 **바이트 단위로 같다** -- 세 키가 빠지면 깨진다."""
    body = {
        "nodes": [
            _n("s", "START"),
            {
                **_n("c", "CONDITION"),
                "condition_path": "input.n",
                "condition_operator": "gt",
                "condition_value": 3,
            },
            _n("t", "END"),
            _n("f", "END"),
        ],
        "edges": [_e("s", "c"), _e("c", "t", "true"), _e("c", "f", "false")],
    }
    created = client.post(
        "/workflows", json={"name": f"wf-{uuid.uuid4()}", **body}, headers=auth_headers
    )
    assert created.status_code == 201, created.text

    stored = client.get(
        f"/workflows/{created.json()['id']}/versions/1", headers=auth_headers
    ).json()

    by_id = {n["id"]: n for n in stored["nodes"]}
    assert by_id["c"]["condition_operator"] == "gt"
    assert by_id["c"]["condition_value"] == 3
    assert serialize_version(_as_version(1, stored)) == serialize_version(_as_version(1, body))


def test_a_version_stored_before_the_condition_keys_is_still_readable(
    client: TestClient,
    auth_headers: dict[str, str],
    admin_connection_factory: _Factory,
) -> None:
    """P4-2a B1 이 `agent_id` 키로 한 번 놓친 함정: 세 키가 없는 옛 행을 `KeyError` 없이 읽는다."""
    created = client.post(
        "/workflows", json={"name": f"wf-{uuid.uuid4()}", **_V1}, headers=auth_headers
    )
    workflow_id = created.json()["id"]
    legacy = [
        {"id": "s", "kind": "START", "max_iterations": None},
        {"id": "e", "kind": "END", "max_iterations": None},
    ]
    conn = admin_connection_factory()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO control.workflow_versions (workflow_id, version, nodes, edges)"
                " VALUES (%s, 2, %s, %s)",
                (
                    workflow_id,
                    json.dumps(legacy),
                    json.dumps([{"source": "s", "target": "e", "label": None}]),
                ),
            )
        conn.commit()
    finally:
        conn.close()

    response = client.get(f"/workflows/{workflow_id}/versions/2", headers=auth_headers)

    assert response.status_code == 200, response.text
    assert [n["condition_path"] for n in response.json()["nodes"]] == [None, None]


def test_invalid_graph_is_400_stores_nothing_and_names_the_reason(
    client: TestClient,
    auth_headers: dict[str, str],
    admin_connection_factory: _Factory,
) -> None:
    """spec 0005 R-1: 잘못된 그래프의 POST 는 4xx 이고 사유가 응답에 있고 저장은 없다."""
    name = f"bad-{uuid.uuid4()}"
    response = client.post(
        "/workflows",
        json={"name": name, "nodes": [_n("a", "AGENT"), _n("e", "END")], "edges": [_e("a", "e")]},
        headers=auth_headers,
    )

    assert response.status_code == 400, response.text
    assert response.json()["violations"] == [{"reason": "no_start", "node_id": None}]
    conn = admin_connection_factory()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM control.workflows WHERE name = %s", (name,))
            row = cur.fetchone()
            assert row is not None and row[0] == 0
    finally:
        conn.close()


def test_unknown_workflow_is_404(client: TestClient, auth_headers: dict[str, str]) -> None:
    assert client.get(f"/workflows/{uuid.uuid4()}", headers=auth_headers).status_code == 404
    put = client.put(f"/workflows/{uuid.uuid4()}", json=_V2, headers=auth_headers)
    assert put.status_code == 404
    assert put.json() == {"detail": "workflow_not_found"}


def test_concurrent_put_serializes_into_consecutive_versions(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    """spec 0005 D-12: 동시 PUT 은 `FOR UPDATE` 로 직렬화되어 번호가 겹치지도 비지도 않는다."""
    workflow_id = client.post(
        "/workflows", json={"name": f"wf-{uuid.uuid4()}", **_V1}, headers=auth_headers
    ).json()["id"]
    count = 4
    results: list[int] = [0] * count

    def _put(i: int) -> None:
        results[i] = client.put(
            f"/workflows/{workflow_id}", json=_V2, headers=auth_headers
        ).status_code

    threads = [threading.Thread(target=_put, args=(i,)) for i in range(count)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert results == [200] * count, results
    current = client.get(f"/workflows/{workflow_id}", headers=auth_headers).json()
    assert current["current_version"] == 1 + count
    for n in range(1, count + 2):
        got = client.get(f"/workflows/{workflow_id}/versions/{n}", headers=auth_headers)
        assert got.status_code == 200, n
