"""spec 0005 2.6 개정 5 (3), R-12 (P4-4): `PostgresApprovalReader` -- 실제 PostgreSQL,
**`aether_data` 역할**로 접속한다.

증명하는 것: 저장된 승인은 읽히고 없는 것은 `None` / **승인 기록의 Run 과 노드 실행의 Run 이 다르면
승인으로 치지 않는다**(API 를 거치지 않고 잘못 심어진 행이 다른 Run 을 전진시키지 못한다) / 읽는
어댑터는 승인 주체(`approved_by`)를 읽지 않는다(권한 판정의 자리를 만들지 않는다, C-4) / 어댑터는
읽기만 한다(쓰기 SQL 이 없다).
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from uuid import UUID, uuid4

import psycopg
import pytest
from aether_workflow.adapters.outbound.db import approval_reader
from aether_workflow.adapters.outbound.db.approval_reader import PostgresApprovalReader
from aether_workflow.domain.approval import Approval
from aether_workflow.domain.node import Edge, Node, NodeKind

from tests.support.workflow_db import declare_workflow_run

pytestmark = pytest.mark.integration

_Factory = Callable[[], psycopg.Connection]


def _run(admin: _Factory) -> UUID:
    run_id, _ = declare_workflow_run(
        admin,
        (Node("s", NodeKind.START), Node("e", NodeKind.END)),
        (Edge("s", "e"),),
    )
    return run_id


def _node_execution(admin: _Factory, workflow_run_id: UUID, node_id: str = "gate") -> UUID:
    conn = admin()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO data.workflow_node_executions (workflow_run_id, node_id, status)"
                " VALUES (%s, %s, 'waiting_approval') RETURNING id",
                (workflow_run_id, node_id),
            )
            row = cur.fetchone()
            assert row is not None
            node_execution_id: UUID = row[0]
        conn.commit()
    finally:
        conn.close()
    return node_execution_id


def _store_approval(
    control: _Factory, workflow_run_id: UUID, node_execution_id: UUID, approved_by: str
) -> None:
    conn = control()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO control.workflow_approvals "
                "(workflow_run_id, node_execution_id, approved_by) VALUES (%s, %s, %s)",
                (workflow_run_id, node_execution_id, approved_by),
            )
        conn.commit()
    finally:
        conn.close()


def test_a_stored_approval_is_read_back_by_the_data_role_and_an_absent_one_is_none(
    admin_connection_factory: _Factory,
    control_connection_factory: _Factory,
    data_connection_factory: _Factory,
) -> None:
    run_id = _run(admin_connection_factory)
    approved = _node_execution(admin_connection_factory, run_id)
    _store_approval(control_connection_factory, run_id, approved, "someone")
    reader = PostgresApprovalReader(data_connection_factory)

    found = reader.approval_for(approved)

    assert isinstance(found, Approval)
    assert found.node_execution_id == approved
    assert found.approved_at is not None
    assert reader.approval_for(uuid4()) is None
    assert reader.approval_for(_node_execution(admin_connection_factory, run_id, "other")) is None


def test_an_approval_recorded_under_another_run_is_not_an_approval_of_this_node_execution(
    admin_connection_factory: _Factory,
    control_connection_factory: _Factory,
    data_connection_factory: _Factory,
) -> None:
    """R-12: 승인 기록의 `workflow_run_id` 가 노드 실행이 속한 Run 과 다르면 근거가 아니다 -- API 는
    이런 행을 만들지 않지만, 실행기는 저장된 사실을 **일관된 것만** 믿는다."""
    run_a = _run(admin_connection_factory)
    run_b = _run(admin_connection_factory)
    node_of_a = _node_execution(admin_connection_factory, run_a)
    _store_approval(control_connection_factory, run_b, node_of_a, "misfiled")
    reader = PostgresApprovalReader(data_connection_factory)

    assert reader.approval_for(node_of_a) is None


def test_the_adapter_reads_neither_the_approver_nor_writes_anything() -> None:
    """C-4: 실행기 쪽 어댑터의 SQL 에 `approved_by`·`note` 가 없고 쓰기 문장이 없다."""
    source = Path(approval_reader.__file__).read_text(encoding="utf-8")
    sql_lines = [
        line
        for line in source.splitlines()
        if line.strip().startswith(("SELECT", "FROM", "WHERE", "JOIN"))
    ]
    assert sql_lines, "SQL 을 찾지 못했다"
    sql = " ".join(sql_lines).lower()
    assert "approved_by" not in sql
    assert "note" not in sql
    for statement in ("insert", "update", "delete"):
        assert statement not in sql
