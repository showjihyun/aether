"""spec 0005 2.7 개정 7, R-9, R-10, D-11 (P4-3 첫 물결): `PARALLEL`/`JOIN`/`LOOP` 의 전체 경로 -
실제 PostgreSQL(`aether_data` 역할) + 실제 Redis.

`api-integration`. 분기·본문은 파킹 없이 끝나는 노드(출력 없는 `PARALLEL` 하나짜리 통과 노드와
판정할 수 없는 `CONDITION`)로 만듭니다 - 이 파일이 보는 것은 **실제 DB 가 회차(`iteration`)·실패·
출력을 받아 적는가** 이고, 파킹과 재개는 단위 테스트(fake)와
`test_workflow_parking_integration.py` 가 봅니다.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any
from uuid import UUID

import psycopg
import pytest
from aether_workflow.adapters.outbound.db.agent_run_reader import PostgresAgentRunReader
from aether_workflow.adapters.outbound.db.approval_reader import PostgresApprovalReader
from aether_workflow.adapters.outbound.db.workflow_run_declaration_reader import (
    PostgresWorkflowRunDeclarationReader,
)
from aether_workflow.adapters.outbound.db.workflow_run_state_store import (
    PostgresWorkflowRunStateStore,
)
from aether_workflow.adapters.outbound.redis.agent_run_launcher import RedisAgentRunLauncher
from aether_workflow.adapters.outbound.redis.workflow_event_sink import RedisWorkflowEventSink
from aether_workflow.adapters.outbound.redis.workflow_status_notifier import (
    RedisWorkflowStatusNotifier,
)
from aether_workflow.adapters.outbound.system_clock import SystemClock
from aether_workflow.application.usecases.advance_workflow_run import AdvanceWorkflowRunUseCase
from aether_workflow.domain.condition import ConditionOperator
from aether_workflow.domain.node import Edge, Node, NodeKind
from aether_workflow.domain.run_status import WorkflowRunStatus
from redis import Redis

from tests.support.workflow_db import declare_workflow_run

pytestmark = pytest.mark.integration


def _noop(node_id: str) -> Node:
    """출력 없이 바로 끝나는 통과 노드: 나가는 간선이 하나뿐인 `PARALLEL`."""
    return Node(node_id, NodeKind.PARALLEL)


def _unevaluable(node_id: str) -> Node:
    """판정할 수 없는 `CONDITION`: 없는 경로에 `equals` 라서 `condition_path_missing` 으로 실패."""
    return Node(
        node_id,
        NodeKind.CONDITION,
        condition_path="input.absent",
        condition_operator=ConditionOperator.EQUALS,
        condition_value="x",
    )


class _Env:
    def __init__(
        self,
        data: Callable[[], psycopg.Connection],
        admin: Callable[[], psycopg.Connection],
        redis_client: Redis,
    ) -> None:
        self.data = data
        self.admin = admin
        self.redis = redis_client

    def advance(self, run_id: UUID) -> WorkflowRunStatus:
        return AdvanceWorkflowRunUseCase(
            PostgresWorkflowRunStateStore(self.data),
            PostgresWorkflowRunDeclarationReader(self.data),
            RedisWorkflowEventSink(self.redis),
            RedisWorkflowStatusNotifier(self.redis),
            SystemClock(),
            agent_runs=PostgresAgentRunReader(self.data),
            approvals=PostgresApprovalReader(self.data),
            launcher=RedisAgentRunLauncher(self.redis),
            owner="worker-a",
            lease_ttl_seconds=60.0,
        )(run_id)

    def declare(
        self,
        nodes: tuple[Node, ...],
        edges: tuple[Edge, ...],
        *,
        input: dict[str, Any] | None = None,
    ) -> UUID:
        run_id, _ = declare_workflow_run(self.admin, nodes, edges, input=input)
        return run_id

    def nodes(self, run_id: UUID) -> list[tuple[str, int, str, str | None]]:
        """`(노드, 회차, 상태, 실패 사유)` - 노드·회차 순."""
        conn = self.admin()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT node_id, iteration, status::text, failure_reason"
                    " FROM data.workflow_node_executions WHERE workflow_run_id = %s"
                    " ORDER BY node_id, iteration",
                    (run_id,),
                )
                return [(r[0], r[1], r[2], r[3]) for r in cur.fetchall()]
        finally:
            conn.close()

    def output(self, run_id: UUID, node_id: str) -> tuple[Any, bool]:
        conn = self.admin()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT output, output_truncated FROM data.workflow_node_executions"
                    " WHERE workflow_run_id = %s AND node_id = %s",
                    (run_id, node_id),
                )
                row = cur.fetchone()
        finally:
            conn.close()
        assert row is not None
        return row[0], row[1]

    def run_row(self, run_id: UUID) -> tuple[str, str | None, str | None]:
        conn = self.admin()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT status::text, failure_reason, lease_owner"
                    " FROM data.workflow_run_executions WHERE workflow_run_id = %s",
                    (run_id,),
                )
                row = cur.fetchone()
        finally:
            conn.close()
        assert row is not None
        return row


@pytest.fixture
def env(
    admin_connection_factory: Callable[[], psycopg.Connection],
    data_connection_factory: Callable[[], psycopg.Connection],
    redis_client: Redis,
) -> _Env:
    return _Env(data_connection_factory, admin_connection_factory, redis_client)


def _diamond(branch_a: Node) -> tuple[tuple[Node, ...], tuple[Edge, ...]]:
    nodes = (
        Node("start", NodeKind.START),
        Node("p", NodeKind.PARALLEL),
        branch_a,
        _noop("b"),
        Node("j", NodeKind.JOIN),
        Node("end", NodeKind.END),
    )
    a_edges: tuple[Edge, ...]
    if branch_a.kind is NodeKind.CONDITION:
        a_edges = (Edge("a", "j", "true"), Edge("a", "j", "false"))
    else:
        a_edges = (Edge("a", "j"),)
    edges = (Edge("start", "p"), Edge("p", "a"), Edge("p", "b"), *a_edges, Edge("b", "j"))
    return nodes, (*edges, Edge("j", "end"))


def test_parallel_branches_join_and_the_run_succeeds_with_one_row_per_node(env: _Env) -> None:
    """R-9: 실제 DB 에서 `START -> PARALLEL -> (a, b) -> JOIN -> END` 가 `succeeded` 이고
    노드 실행은 노드당 1행이다."""
    run_id = env.declare(*_diamond(_noop("a")))

    status = env.advance(run_id)

    assert status is WorkflowRunStatus.SUCCEEDED
    assert env.nodes(run_id) == [
        ("a", 0, "succeeded", None),
        ("b", 0, "succeeded", None),
        ("end", 0, "succeeded", None),
        ("j", 0, "succeeded", None),
        ("p", 0, "succeeded", None),
        ("start", 0, "succeeded", None),
    ]
    assert env.output(run_id, "j") == ({"branches": {"a": None, "b": None}}, False)
    assert env.run_row(run_id) == ("succeeded", None, None)


def test_one_failed_branch_ends_the_run_failed_at_the_join(env: _Env) -> None:
    """R-9: 한 분기가 실패해도 다른 분기는 끝까지 돌고, `JOIN` 이 `branch_failed` 로 Workflow 를
    끝낸다. 실패한 분기의 노드는 자기 사유로 `failed` 로 남는다."""
    run_id = env.declare(*_diamond(_unevaluable("a")), input={"q": "go"})

    status = env.advance(run_id)

    assert status is WorkflowRunStatus.FAILED
    assert env.nodes(run_id) == [
        ("a", 0, "failed", "condition_path_missing"),
        ("b", 0, "succeeded", None),
        ("j", 0, "failed", "branch_failed"),
        ("p", 0, "succeeded", None),
        ("start", 0, "succeeded", None),
    ]
    assert env.output(run_id, "j") == ({"branches": {"a": None, "b": None}}, False)
    assert env.run_row(run_id) == ("failed", "branch_failed", None)


def test_a_loop_over_its_bound_ends_failed_with_one_row_per_pass(env: _Env) -> None:
    """R-10: 상한 2 인 루프가 3 번째 판정에서 `loop_limit_exceeded` 로 끝나고, 본문 노드의
    `iteration` 은 0·1 이다(`unique(run, node, iteration)` 충돌 없이)."""
    nodes = (
        Node("start", NodeKind.START),
        Node(
            "loop",
            NodeKind.LOOP,
            max_iterations=2,
            condition_path="input.q",
            condition_operator=ConditionOperator.EQUALS,
            condition_value="go",
        ),
        _noop("body"),
        Node("end", NodeKind.END),
    )
    edges = (
        Edge("start", "loop"),
        Edge("loop", "body", "true"),
        Edge("body", "loop"),
        Edge("loop", "end", "false"),
    )
    run_id = env.declare(nodes, edges, input={"q": "go"})

    status = env.advance(run_id)

    assert status is WorkflowRunStatus.FAILED
    assert env.nodes(run_id) == [
        ("body", 0, "succeeded", None),
        ("body", 1, "succeeded", None),
        ("loop", 0, "succeeded", None),
        ("loop", 1, "succeeded", None),
        ("loop", 2, "failed", "loop_limit_exceeded"),
        ("start", 0, "succeeded", None),
    ]
    assert env.run_row(run_id) == ("failed", "loop_limit_exceeded", None)
