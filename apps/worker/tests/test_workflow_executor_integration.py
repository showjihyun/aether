"""spec 0005 2.3, 2.9 개정 2, 2.10, R-6(절반), R-8, D-13 (P4-2a A): 실행기 골격의 전체 경로 -
실제 PostgreSQL(`aether_data` 역할) + 실제 Redis. `START` -> `END` Workflow 를 선언하고 전진시킨다.

구성은 `main._build_production_workflow_handler` 가 하는 것과 같은 어댑터를 손으로 꽂은 것입니다
(조립 자체는 `test_build_production_handler_wires_workflow.py` 가 증명합니다). `START` -> `END`
에는 파킹이 없으므로 전진이 끝난 뒤 lease 열은 **비어** 있어야 합니다. `AGENT` 노드와 파킹은
`test_workflow_parking_integration.py` 가 봅니다(P4-2a B2).
"""

from __future__ import annotations

from collections.abc import Callable
from uuid import UUID, uuid4

import psycopg
import pytest
from aether_worker.adapters.outbound.noop_trace_context import NoopTraceContext
from aether_worker.application.ports.inbound.handle_workflow_requested import (
    WorkflowRequestedMessage,
)
from aether_worker.application.usecases.handle_workflow_requested import (
    HandleWorkflowRequestedUseCase,
)
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
from aether_workflow.application.ports.inbound.advance_workflow_run import WorkflowLeaseHeld
from aether_workflow.application.usecases.advance_workflow_run import AdvanceWorkflowRunUseCase
from aether_workflow.domain.events import WorkflowEvent
from aether_workflow.domain.node import Edge, Node, NodeKind
from aether_workflow.domain.node_execution import NodeExecutionStatus
from aether_workflow.domain.run_status import WorkflowRunStatus
from redis import Redis

from tests.support.workflow_db import declare_workflow_run

pytestmark = pytest.mark.integration

_START_END = (
    (Node("start", NodeKind.START), Node("end", NodeKind.END)),
    (Edge("start", "end"),),
)
_STATUS_STREAM = "aether:workflow_runs:status"


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
        self.store = PostgresWorkflowRunStateStore(data)

    def advance_as(self, owner: str) -> AdvanceWorkflowRunUseCase:
        return AdvanceWorkflowRunUseCase(
            self.store,
            PostgresWorkflowRunDeclarationReader(self.data),
            RedisWorkflowEventSink(self.redis),
            RedisWorkflowStatusNotifier(self.redis),
            SystemClock(),
            agent_runs=PostgresAgentRunReader(self.data),
            approvals=PostgresApprovalReader(self.data),
            launcher=RedisAgentRunLauncher(self.redis),
            owner=owner,
            lease_ttl_seconds=60.0,
        )

    def declare(self) -> UUID:
        run_id, _ = declare_workflow_run(self.admin, *_START_END)
        return run_id

    def row(self, run_id: UUID) -> tuple[str, int, str | None, str | None, object, object]:
        conn = self.admin()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT status::text, status_seq, current_node_id, lease_owner,
                           lease_until, finished_at
                    FROM data.workflow_run_executions WHERE workflow_run_id = %s
                    """,
                    (run_id,),
                )
                row = cur.fetchone()
        finally:
            conn.close()
        assert row is not None
        return row

    def node_rows(self, run_id: UUID) -> list[tuple[str, str]]:
        conn = self.admin()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT node_id, status FROM data.workflow_node_executions
                    WHERE workflow_run_id = %s ORDER BY started_at, node_id
                    """,
                    (run_id,),
                )
                return [(r[0], r[1]) for r in cur.fetchall()]
        finally:
            conn.close()

    def events(self, run_id: UUID) -> list[tuple[str, WorkflowEvent]]:
        raw = self.redis.xrange(f"aether:workflow_runs:{run_id}:events", min="-", max="+")
        assert raw is not None
        return [
            (str(entry_id), WorkflowEvent.model_validate_json(str((fields or {})["data"])))
            for entry_id, fields in raw
        ]

    def status_messages(self, run_id: UUID) -> list[dict[str, str]]:
        raw = self.redis.xrange(_STATUS_STREAM, min="-", max="+")
        assert raw is not None
        messages = [{str(k): str(v) for k, v in (fields or {}).items()} for _, fields in raw]
        return [m for m in messages if m["workflow_run_id"] == str(run_id)]


@pytest.fixture
def env(
    admin_connection_factory: Callable[[], psycopg.Connection],
    data_connection_factory: Callable[[], psycopg.Connection],
    redis_client: Redis,
) -> _Env:
    return _Env(data_connection_factory, admin_connection_factory, redis_client)


def test_start_to_end_succeeds_with_two_node_rows_monotonic_status_and_four_event_types(
    env: _Env,
) -> None:
    run_id = env.declare()

    status = env.advance_as("worker-a")(run_id)

    assert status is WorkflowRunStatus.SUCCEEDED
    db_status, status_seq, current_node_id, _, _, finished_at = env.row(run_id)
    assert (db_status, status_seq, current_node_id) == ("succeeded", 7, "end")
    assert finished_at is not None
    assert env.node_rows(run_id) == [("start", "succeeded"), ("end", "succeeded")]

    messages = env.status_messages(run_id)
    seqs = [int(m["seq"]) for m in messages]
    assert seqs == [1, 6]
    assert [m["status"] for m in messages] == ["running", "succeeded"]

    events = env.events(run_id)
    assert [entry_id for entry_id, _ in events] == [f"{n}-0" for n in range(1, 8)]
    assert {e.type for _, e in events} == {
        "workflow.status",
        "node.started",
        "node.finished",
        "workflow.finished",
    }
    assert [e.seq for _, e in events] == list(range(1, 8))


def test_the_same_request_handled_twice_leaves_one_row_per_node(env: _Env) -> None:
    """R-8: 같은 요청을 두 번 처리해도 노드 실행 행이 노드당 1행 - 종결 뒤 재전달과, 상태를 되돌려
    다시 전진시키는 재개 두 경우 모두."""
    run_id = env.declare()
    handler = HandleWorkflowRequestedUseCase(env.advance_as("worker-a"), NoopTraceContext())
    message = WorkflowRequestedMessage("1-0", run_id, uuid4(), None)

    first = handler(message)
    second = handler(message)

    assert first.ack and second.ack
    assert second.status is WorkflowRunStatus.SUCCEEDED
    assert env.node_rows(run_id) == [("start", "succeeded"), ("end", "succeeded")]
    assert len(env.events(run_id)) == 7, "두 번째 처리는 이벤트를 더하지 않는다"

    # 종결 상태를 지우고(재개를 흉내) 다시 전진시켜도 마친 노드는 다시 실행되지 않는다.
    conn = env.admin()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE data.workflow_run_executions SET status = 'running', finished_at = NULL"
                " WHERE workflow_run_id = %s",
                (run_id,),
            )
        conn.commit()
    finally:
        conn.close()
    node_ids_before = {r.node_id: r.id for r in env.store.node_executions(run_id)}

    again = handler(message)

    assert again.status is WorkflowRunStatus.SUCCEEDED
    assert env.node_rows(run_id) == [("start", "succeeded"), ("end", "succeeded")]
    assert {r.node_id: r.id for r in env.store.node_executions(run_id)} == node_ids_before
    started_events = [e for _, e in env.events(run_id) if e.type == "node.started"]
    assert len(started_events) == 2, "마친 노드의 node.started 를 다시 내지 않는다"


def test_a_new_owner_resumes_after_a_crash_without_rerunning_the_finished_node(
    env: _Env,
) -> None:
    """R-6 의 절반: 노드 하나를 마친 상태에서 worker 가 죽고(lease 만료), 새 owner 가 이어받아
    END 에 닿는다 - 마친 START 의 실행 기록은 같은 행 하나로 남는다."""
    run_id = env.declare()
    # "죽은 worker": lease 를 잡고 START 를 마친 뒤 release 하지 못했다.
    assert env.store.acquire_lease(run_id, "dead-worker", 60.0)
    env.store.set_status(run_id, WorkflowRunStatus.RUNNING, seq=1, started_at=SystemClock().now())
    start_id = env.store.start_node(run_id, "start", 0)
    assert start_id is not None
    env.store.set_status(run_id, WorkflowRunStatus.RUNNING, seq=2, current_node_id="start")
    env.store.finish_node(start_id, NodeExecutionStatus.SUCCEEDED, SystemClock().now())
    conn = env.admin()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE data.workflow_run_executions"
                " SET lease_until = now() - interval '1 second' WHERE workflow_run_id = %s",
                (run_id,),
            )
        conn.commit()
    finally:
        conn.close()

    status = env.advance_as("worker-new")(run_id)

    assert status is WorkflowRunStatus.SUCCEEDED
    assert env.node_rows(run_id) == [("start", "succeeded"), ("end", "succeeded")]
    records = {r.node_id: r for r in env.store.node_executions(run_id)}
    assert records["start"].id == start_id, "마친 노드의 기록은 새 행으로 바뀌지 않는다"
    started = [e.payload["node_id"] for _, e in env.events(run_id) if e.type == "node.started"]
    assert started == ["end"]
    seqs = [e.seq for _, e in env.events(run_id)]
    assert seqs[0] == 3 and seqs == sorted(seqs), "seq 는 저장된 status_seq 에서 이어진다"


def test_a_lease_held_by_another_owner_raises_and_leaves_the_lease_columns_alone(
    env: _Env,
) -> None:
    run_id = env.declare()
    assert env.store.acquire_lease(run_id, "other-worker", 60.0)
    before = env.row(run_id)

    with pytest.raises(WorkflowLeaseHeld):
        env.advance_as("worker-a")(run_id)

    after = env.row(run_id)
    assert after[3] == "other-worker"
    assert after[4] == before[4], "lease_until 도 그대로"
    assert after[0] == "queued"
    assert env.node_rows(run_id) == []
    assert env.events(run_id) == []
    assert env.status_messages(run_id) == []


def test_lease_columns_are_empty_after_the_advance_finishes(env: _Env) -> None:
    """파킹이 아니라 종료 - lease 가 비어 있다(PR B 의 R-7 이 이 자리에 얹힌다)."""
    run_id = env.declare()

    env.advance_as("worker-a")(run_id)

    _, _, _, lease_owner, lease_until, _ = env.row(run_id)
    assert lease_owner is None
    assert lease_until is None


def test_an_unsupported_node_kind_ends_failed_with_the_reason_persisted_and_notified(
    env: _Env,
) -> None:
    """plan 부록 A: 지원하지 않는 종류는 `failed` + 구별되는 사유 - DB 와 통지에 남는다."""
    run_id, _ = declare_workflow_run(
        env.admin,
        (Node("start", NodeKind.START), Node("a", NodeKind.WAIT), Node("end", NodeKind.END)),
        (Edge("start", "a"), Edge("a", "end")),
    )

    status = env.advance_as("worker-a")(run_id)

    assert status is WorkflowRunStatus.FAILED
    conn = env.admin()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT status::text, failure_reason, current_node_id, lease_owner"
                " FROM data.workflow_run_executions WHERE workflow_run_id = %s",
                (run_id,),
            )
            row = cur.fetchone()
    finally:
        conn.close()
    assert row == ("failed", "unsupported_node_kind", "a", None)
    assert env.node_rows(run_id) == [("start", "succeeded")]
    last = env.status_messages(run_id)[-1]
    assert last["status"] == "failed"
    assert last["failure_reason"] == "unsupported_node_kind"
    assert last["current_node_id"] == "a"
