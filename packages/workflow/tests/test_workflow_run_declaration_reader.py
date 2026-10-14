"""spec 0005 2.3, 2.9 개정 2: `PostgresWorkflowRunDeclarationReader` - worker 역할(`aether_data`)이
`control.workflow_runs` + `control.workflow_versions` 를 JOIN 해 읽고, 노드·간선을 도메인
값 객체로 복원한다. 쓰기는 하지 않는다.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from uuid import uuid4

import psycopg
import pytest
from aether_workflow.adapters.outbound.db.workflow_run_declaration_reader import (
    PostgresWorkflowRunDeclarationReader,
)
from aether_workflow.domain.node import Edge, Node, NodeKind

from tests.support.workflow_db import declare_workflow_run, issue_api_key

pytestmark = pytest.mark.integration


def test_reads_nodes_edges_input_and_version(
    admin_connection_factory: Callable[[], psycopg.Connection],
    data_connection_factory: Callable[[], psycopg.Connection],
) -> None:
    nodes = (Node("s", NodeKind.START), Node("l", NodeKind.LOOP, 3), Node("e", NodeKind.END))
    edges = (Edge("s", "l"), Edge("l", "e", "done"))
    run_id, version_id = declare_workflow_run(
        admin_connection_factory, nodes, edges, input={"topic": "x"}
    )

    declaration = PostgresWorkflowRunDeclarationReader(data_connection_factory).declaration(run_id)

    assert declaration is not None
    assert declaration.workflow_run_id == run_id
    assert declaration.workflow_version_id == version_id
    assert declaration.version_number == 1
    assert declaration.nodes == nodes
    assert declaration.edges == edges
    assert declaration.input == {"topic": "x"}
    assert declaration.cancel_requested_at is None


def test_unknown_run_is_none(
    data_connection_factory: Callable[[], psycopg.Connection],
) -> None:
    reader = PostgresWorkflowRunDeclarationReader(data_connection_factory)
    assert reader.declaration(uuid4()) is None


def test_reads_the_agent_reference_and_the_requester(
    admin_connection_factory: Callable[[], psycopg.Connection],
    data_connection_factory: Callable[[], psycopg.Connection],
) -> None:
    """B2: `AGENT` 노드의 `agent_id`·`agent_version` 이 도메인 값으로 복원되고(B1 이 직렬화에 더한
    키), 요청자는 `control.workflow_runs.requested_by`(0007)에서 온다."""
    agent_id = uuid4()
    nodes = (
        Node("s", NodeKind.START),
        Node("a", NodeKind.AGENT, agent_id=agent_id, agent_version=2),
        Node("b", NodeKind.AGENT, agent_id=agent_id),
        Node("e", NodeKind.END),
    )
    edges = (Edge("s", "a"), Edge("a", "b"), Edge("b", "e"))
    key = issue_api_key(admin_connection_factory)
    run_id, _ = declare_workflow_run(admin_connection_factory, nodes, edges, requested_by=key)

    declaration = PostgresWorkflowRunDeclarationReader(data_connection_factory).declaration(run_id)

    assert declaration is not None
    assert declaration.nodes == nodes
    assert declaration.requested_by == key


def test_a_run_without_requester_reads_as_none(
    admin_connection_factory: Callable[[], psycopg.Connection],
    data_connection_factory: Callable[[], psycopg.Connection],
) -> None:
    """0007 이전 행 - 요청자 열이 NULL. 실행기가 이것을 보고 `AGENT` 노드를 실패시킨다."""
    run_id, _ = declare_workflow_run(
        admin_connection_factory,
        (Node("s", NodeKind.START), Node("e", NodeKind.END)),
        (Edge("s", "e"),),
    )

    declaration = PostgresWorkflowRunDeclarationReader(data_connection_factory).declaration(run_id)

    assert declaration is not None
    assert declaration.requested_by is None


def test_nodes_stored_before_the_agent_keys_existed_still_read(
    admin_connection_factory: Callable[[], psycopg.Connection],
    data_connection_factory: Callable[[], psycopg.Connection],
) -> None:
    """A 가 만든 Version 의 노드 JSON 에는 `agent_id`·`agent_version` 키가 **없다** - `KeyError` 로
    터지지 않고 `None` 이다. Version 은 불변이라 옛 모양을 INSERT 로 직접 심는다."""
    old_nodes = [
        {"id": "s", "kind": "START", "max_iterations": None},
        {"id": "e", "kind": "END", "max_iterations": None},
    ]
    conn = admin_connection_factory()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO control.workflows (name) VALUES (%s) RETURNING id",
                (f"legacy-{uuid4()}",),
            )
            row = cur.fetchone()
            assert row is not None
            cur.execute(
                "INSERT INTO control.workflow_versions (workflow_id, version, nodes, edges) "
                "VALUES (%s, 1, %s, %s) RETURNING id",
                (
                    row[0],
                    json.dumps(old_nodes),
                    json.dumps([{"source": "s", "target": "e", "label": None}]),
                ),
            )
            version = cur.fetchone()
            assert version is not None
            cur.execute(
                "INSERT INTO control.workflow_runs (workflow_version_id) VALUES (%s) RETURNING id",
                (version[0],),
            )
            run = cur.fetchone()
            assert run is not None
        conn.commit()
    finally:
        conn.close()

    declaration = PostgresWorkflowRunDeclarationReader(data_connection_factory).declaration(run[0])

    assert declaration is not None
    assert [(n.agent_id, n.agent_version) for n in declaration.nodes] == [(None, None)] * 2
