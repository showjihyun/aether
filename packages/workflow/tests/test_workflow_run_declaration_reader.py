"""spec 0005 2.3, 2.9 개정 2: `PostgresWorkflowRunDeclarationReader` - worker 역할(`aether_data`)이
`control.workflow_runs` + `control.workflow_versions` 를 JOIN 해 읽고, 노드·간선을 도메인
값 객체로 복원한다. 쓰기는 하지 않는다.
"""

from __future__ import annotations

from collections.abc import Callable
from uuid import uuid4

import psycopg
import pytest
from aether_workflow.adapters.outbound.db.workflow_run_declaration_reader import (
    PostgresWorkflowRunDeclarationReader,
)
from aether_workflow.domain.node import Edge, Node, NodeKind

from tests.support.workflow_db import declare_workflow_run

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
