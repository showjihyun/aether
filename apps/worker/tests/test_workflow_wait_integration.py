"""spec 0005 2.7 개정 7 (5), R-11, D-4 (P4-3 둘째 물결): `WAIT` 의 전체 경로 -- 실제 PostgreSQL
(`aether_data` 역할) + 실제 Redis.

`api-integration`. 구성은 `test_workflow_parking_integration.py` 와 같은 어댑터를 손으로 꽂은
것입니다. **시간을 기다리지 않습니다**: `wake_at` 을 과거로 바꿔 "시간이 지난" 상태를 만듭니다.

증명하는 것 (`START -> WAIT -> END`):
- `wake_at` 전에는 `waiting_timer` 로 멈추고 lease 는 비어 있다(R-7). 이른 깨움(중복 메시지)과
  스위퍼 모두 아무 것도 바꾸지 않는다.
- `wake_at` 을 과거로 만든 뒤 **`sweep_once()` 만으로** 재큐되고 재개되어 `succeeded` 가 된다 --
  `WAIT` 에는 깨우는 외부 사건이 없어서 스위퍼가 안전망이 아니라 **주 경로**라는 판정이다.
- 끝난 Workflow 는 다시 줍지 않는다. `wake_at` 은 `waiting_timer` 일 때만 값이 있다.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from uuid import UUID

import psycopg
import pytest
from aether_worker.adapters.inbound.schedule.workflow_sweeper import WorkflowSweeper
from aether_worker.adapters.outbound.db.parked_workflow_finder import PostgresParkedWorkflowFinder
from aether_worker.adapters.outbound.noop_trace_context import NoopTraceContext
from aether_worker.adapters.outbound.redis.workflow_requeuer import RedisWorkflowRequeuer
from aether_worker.application.ports.inbound.handle_workflow_requested import (
    WorkflowRequestedMessage,
)
from aether_worker.application.usecases.handle_workflow_requested import (
    HandleWorkflowRequestedUseCase,
)
from aether_worker.application.usecases.resume_parked_workflows import (
    ResumeParkedWorkflowsUseCase,
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
from aether_workflow.application.usecases.advance_workflow_run import AdvanceWorkflowRunUseCase
from aether_workflow.domain.node import Edge, Node, NodeKind
from aether_workflow.domain.run_status import WorkflowRunStatus
from redis import Redis

from tests.support.redis import stream_entries
from tests.support.workflow_db import declare_workflow_run

pytestmark = pytest.mark.integration

_Factory = Callable[[], psycopg.Connection]
_REQUEST_STREAM = "aether:workflow_runs:requested"


class _Env:
    def __init__(self, data: _Factory, admin: _Factory, redis_client: Redis) -> None:
        self.data = data
        self.admin = admin
        self.redis = redis_client
        self._retire_leftover_parked_runs()
        self._consumed = "0-0"
        self.sweeper = WorkflowSweeper(
            ResumeParkedWorkflowsUseCase(
                PostgresParkedWorkflowFinder(data), RedisWorkflowRequeuer(redis_client)
            ),
            interval_seconds=30.0,
        )

    def _retire_leftover_parked_runs(self) -> None:
        """DB 는 세션 안에서 공유된다 -- 앞선 테스트가 남긴 대기 Run 이 있으면 `sweep()` 이 그것까지
        줍는다. 이 파일의 단언은 **자기 Run** 만 센다."""
        conn = self.admin()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE data.workflow_run_executions SET status = 'cancelled'"
                    " WHERE status IN ('waiting_run', 'waiting_approval', 'waiting_timer')"
                )
            conn.commit()
        finally:
            conn.close()

    def advance_as(self, owner: str) -> AdvanceWorkflowRunUseCase:
        return AdvanceWorkflowRunUseCase(
            PostgresWorkflowRunStateStore(self.data),
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

    def drain_requests(self, owner: str) -> list[UUID]:
        """`aether:workflow_runs:requested` 에 새로 쌓인 요청을 전부 실행기에 건넨다 -- 소비자가
        하는 일을 결정적으로 흉내 낸다. 건넨 Workflow Run id 를 돌려준다."""
        handler = HandleWorkflowRequestedUseCase(self.advance_as(owner), NoopTraceContext())
        handled: list[UUID] = []
        for entry_id, fields in stream_entries(self.redis, _REQUEST_STREAM, after=self._consumed):
            self._consumed = entry_id
            run_id = UUID(fields["workflow_run_id"])
            handler(
                WorkflowRequestedMessage(
                    entry_id, run_id, UUID(fields["workflow_version_id"]), None
                )
            )
            handled.append(run_id)
        return handled

    def declare(self, wait_seconds: int) -> UUID:
        run_id, _ = declare_workflow_run(
            self.admin,
            (
                Node("start", NodeKind.START),
                Node("w", NodeKind.WAIT, wait_seconds=wait_seconds),
                Node("end", NodeKind.END),
            ),
            (Edge("start", "w"), Edge("w", "end")),
        )
        return run_id

    def execution(self, run_id: UUID) -> tuple[str, int, datetime | None, str | None]:
        """`(상태, status_seq, wake_at, lease_owner)`."""
        conn = self.admin()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT status::text, status_seq, wake_at, lease_owner"
                    " FROM data.workflow_run_executions WHERE workflow_run_id = %s",
                    (run_id,),
                )
                row = cur.fetchone()
        finally:
            conn.close()
        assert row is not None
        return (row[0], row[1], row[2], row[3])

    def nodes(self, run_id: UUID) -> list[tuple[str, str]]:
        conn = self.admin()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT node_id, status::text FROM data.workflow_node_executions"
                    " WHERE workflow_run_id = %s ORDER BY started_at, node_id",
                    (run_id,),
                )
                return [(r[0], r[1]) for r in cur.fetchall()]
        finally:
            conn.close()

    def wake_in_the_past(self, run_id: UUID) -> None:
        """시간이 지난 것으로 만든다 -- 실제로 기다리지 않는다."""
        conn = self.admin()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE data.workflow_run_executions SET wake_at = now() - interval '1 minute'"
                    " WHERE workflow_run_id = %s",
                    (run_id,),
                )
            conn.commit()
        finally:
            conn.close()


@pytest.fixture
def env(
    admin_connection_factory: _Factory,
    data_connection_factory: _Factory,
    redis_client: Redis,
) -> _Env:
    return _Env(data_connection_factory, admin_connection_factory, redis_client)


def test_start_wait_end_stops_at_waiting_timer_and_the_sweeper_alone_resumes_it(env: _Env) -> None:
    """R-11, 개정 7 (5): `wake_at` 전에는 `waiting_timer` 로 멈추고, `wake_at` 을 과거로 만든 뒤
    `sweep_once()` **만으로** 재개되어 `succeeded` 가 된다 - 스위퍼가 주 경로다."""
    run_id = env.declare(3600)

    parked = env.advance_as("worker-a")(run_id)

    assert parked is WorkflowRunStatus.WAITING_TIMER
    status, seq, wake_at, lease_owner = env.execution(run_id)
    assert (status, lease_owner) == ("waiting_timer", None), "R-7: 대기 중에 lease 를 쥐지 않는다"
    assert wake_at is not None
    assert env.nodes(run_id) == [("start", "succeeded"), ("w", "waiting_timer")]

    # wake_at 전: 스위퍼도, 이른 깨움(중복 메시지)도 아무 것도 바꾸지 않는다.
    assert env.sweeper.sweep_once() == 0
    early = env.advance_as("worker-b")(run_id)
    assert early is WorkflowRunStatus.WAITING_TIMER
    assert env.execution(run_id)[:3] == (status, seq, wake_at)
    assert env.nodes(run_id) == [("start", "succeeded"), ("w", "waiting_timer")]

    # 시간이 지났다: 스위퍼가 주워 재큐하고 요청을 처리하면 END 에 닿는다.
    env.wake_in_the_past(run_id)
    assert env.sweeper.sweep_once() == 1
    assert env.drain_requests("worker-c") == [run_id]

    status, seq_after, wake_after, lease_after = env.execution(run_id)
    assert (status, wake_after, lease_after) == ("succeeded", None, None)
    assert seq_after > seq
    assert env.nodes(run_id) == [
        ("start", "succeeded"),
        ("w", "succeeded"),
        ("end", "succeeded"),
    ]
    assert env.sweeper.sweep_once() == 0, "끝난 Workflow 는 더 이상 줍지 않는다"


def test_the_same_wake_up_twice_advances_the_node_once(env: _Env) -> None:
    """R-8: 스위퍼가 두 번 재큐해도(두 주기 사이에 처리가 늦은 경우) 노드는 한 번만 마친다 -
    노드 실행 기록은 노드당 1행이다."""
    run_id = env.declare(3600)
    env.advance_as("worker-a")(run_id)
    env.wake_in_the_past(run_id)

    assert env.sweeper.sweep_once() == 1
    assert env.sweeper.sweep_once() == 1, "아직 처리 전이라 한 번 더 줍는다"
    assert env.drain_requests("worker-b") == [run_id, run_id]

    assert env.execution(run_id)[0] == "succeeded"
    assert len(env.nodes(run_id)) == 3
