"""spec 0005 2.5 개정 3, R-6, R-7, R-8, D-4 (P4-2a B2): `AGENT` 노드의 파킹과 재개 -- 실제
PostgreSQL(`aether_data` 역할) + 실제 Redis.

`api-integration`. 구성은 `main._build_production_workflow_handler`·`_build_production_resume` 가
하는 것과 같은 어댑터를 손으로 꽂은 것이고(조립 자체는 `test_build_production_handler_wires_
workflow.py` 가 증명), **자식 Agent Run 은 api·worker 를 거치지 않고 DB 행으로 흉내** 냅니다 --
`control.runs` 선언(api 의 일)과 `data.run_executions` 상태(Agent Run 실행기의 일)를 직접 씁니다.
진짜 api 와 진짜 Agent Run 실행기가 맞물리는 것은
`apps/api/tests/test_workflow_chain_integration.py`
가 봅니다.

증명하는 것:
- R-6: 파킹까지 간 뒤 **다른 owner**(프로세스 재시작)가 자식 종결 뒤 이어받아 END 에 닿고, 노드 실행
  기록은 노드당 1행.
- R-7: 파킹된 Workflow Run 여럿의 lease 열이 **비어** 있고, 평범한 Agent Run 이 정상 처리됨.
- R-8: 같은 요청 메시지를 두 번, 빠른 경로와 스위퍼가 둘 다 재큐해도 자식 Run 발사 1건·노드 1행.
- 스위퍼만으로 재개: 종결 통지가 **한 건도 없어도** `sweep_once()` 하나로 END 에 닿는다.
"""

from __future__ import annotations

import json
import threading
import uuid
from collections.abc import Callable
from typing import Any
from uuid import UUID, uuid4

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
from aether_worker.main import serve
from aether_worker.settings import Settings
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

from tests.support.pg import DATA_PASSWORD, DATA_ROLE
from tests.support.redis import stream_entries
from tests.support.waiting import wait_until
from tests.support.workflow_db import declare_workflow_run, issue_api_key

pytestmark = pytest.mark.integration

_Factory = Callable[[], psycopg.Connection]
_LAUNCH_STREAM = "aether:workflow:agent_runs:requested"
_REQUEST_STREAM = "aether:workflow_runs:requested"
_DEFINITION = {
    "schema_version": 1,
    "system_prompt": "You are a careful assistant.",
    "model": {"id": "test-model"},
    "tools": [],
    "policy": {"timeout_seconds": 120, "max_steps": 8, "model_retries": 0, "tool_retries": 0},
}


class _Env:
    def __init__(self, data: _Factory, admin: _Factory, redis_client: Redis) -> None:
        self.data = data
        self.admin = admin
        self.redis = redis_client
        self._retire_leftover_parked_runs()
        self.key = issue_api_key(admin)
        self.agent_id, self.agent_version_id = self._agent()
        self._consumed = "0-0"

    def _retire_leftover_parked_runs(self) -> None:
        """DB 는 세션 안에서 공유된다 -- 앞선 테스트(파킹 어댑터 테스트 등)가 `waiting_run` 으로
        남긴
        Run 이 있으면 `sweep()` 이 그것까지 줍는다(P4-4: 승인이 저장된 `waiting_approval` 도
        줍는다). 이 파일의 단언은 **자기 Run** 만 센다: 남은 것을
        종결 처리해 스위퍼의 입력에서 치운다."""
        conn = self.admin()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE data.workflow_run_executions SET status = 'cancelled'"
                    " WHERE status IN ('waiting_run', 'waiting_approval')"
                )
            conn.commit()
        finally:
            conn.close()

    # -- 조립 ---------------------------------------------------------------------

    def advance_as(self, owner: str) -> AdvanceWorkflowRunUseCase:
        """프로세스 하나 -- 새 인스턴스·다른 owner 가 "재시작" 이다."""
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

    def resume(self) -> ResumeParkedWorkflowsUseCase:
        return ResumeParkedWorkflowsUseCase(
            PostgresParkedWorkflowFinder(self.data), RedisWorkflowRequeuer(self.redis)
        )

    def drain_requests(self, owner: str) -> list[WorkflowRequestedMessage]:
        """`aether:workflow_runs:requested` 에 새로 쌓인 요청을 전부 실행기에 건넨다 -- 소비자가
        하는 일(읽고 handler 를 부름)을 결정적으로 흉내 낸다."""
        handler = HandleWorkflowRequestedUseCase(self.advance_as(owner), NoopTraceContext())
        entries = stream_entries(self.redis, _REQUEST_STREAM, after=self._consumed)
        handled: list[WorkflowRequestedMessage] = []
        for entry_id, fields in entries:
            self._consumed = entry_id
            message = WorkflowRequestedMessage(
                entry_id,
                UUID(fields["workflow_run_id"]),
                UUID(fields["workflow_version_id"]),
                None,
            )
            handler(message)
            handled.append(message)
        return handled

    # -- 심기 ----------------------------------------------------------------------

    def _agent(self) -> tuple[UUID, UUID]:
        conn = self.admin()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO control.agents (name) VALUES (%s) RETURNING id",
                    (f"parking-{uuid4()}",),
                )
                row = cur.fetchone()
                assert row is not None
                agent_id: UUID = row[0]
                cur.execute(
                    "INSERT INTO control.agent_versions (agent_id, version, definition)"
                    " VALUES (%s, 1, %s) RETURNING id",
                    (agent_id, json.dumps(_DEFINITION)),
                )
                version = cur.fetchone()
                assert version is not None
            conn.commit()
        finally:
            conn.close()
        return agent_id, version[0]

    def declare(self, *, input: dict[str, Any] | None = None) -> tuple[UUID, UUID]:
        return declare_workflow_run(
            self.admin,
            (
                Node("start", NodeKind.START),
                Node("a", NodeKind.AGENT, agent_id=self.agent_id),
                Node("end", NodeKind.END),
            ),
            (Edge("start", "a"), Edge("a", "end")),
            input=input,
            requested_by=self.key,
        )

    def request(self, run_id: UUID, version_id: UUID) -> None:
        self.redis.xadd(
            _REQUEST_STREAM,
            {
                "workflow_run_id": str(run_id),
                "workflow_version_id": str(version_id),
                "traceparent": "",
            },
        )

    def finish_child(self, child: UUID, status: str) -> None:
        """api 가 선언하고 Agent Run 실행기가 끝낸 것을 흉내: `control.runs` 선언 +
        `data.run_executions`."""
        conn = self.admin()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO control.runs (id, agent_version_id, input, requested_by)"
                    " VALUES (%s, %s, 'x', %s) ON CONFLICT (id) DO NOTHING",
                    (child, self.agent_version_id, self.key),
                )
                cur.execute(
                    "INSERT INTO data.run_executions (run_id, status)"
                    " VALUES (%s, %s::data.run_execution_status)"
                    " ON CONFLICT (run_id) DO UPDATE SET status = EXCLUDED.status",
                    (child, status),
                )
            conn.commit()
        finally:
            conn.close()

    # -- 관측 ----------------------------------------------------------------------

    def launches(self) -> list[dict[str, str]]:
        return [fields for _, fields in stream_entries(self.redis, _LAUNCH_STREAM)]

    def execution(self, run_id: UUID) -> tuple[str, UUID | None, str | None, object]:
        conn = self.admin()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT status::text, waiting_run_id, lease_owner, lease_until"
                    " FROM data.workflow_run_executions WHERE workflow_run_id = %s",
                    (run_id,),
                )
                row = cur.fetchone()
        finally:
            conn.close()
        assert row is not None
        return (row[0], row[1], row[2], row[3])

    def nodes(self, run_id: UUID) -> list[tuple[str, str, UUID | None]]:
        conn = self.admin()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT node_id, status::text, agent_run_id FROM data.workflow_node_executions"
                    " WHERE workflow_run_id = %s ORDER BY started_at, node_id",
                    (run_id,),
                )
                return [(r[0], r[1], r[2]) for r in cur.fetchall()]
        finally:
            conn.close()

    def child_of(self, run_id: UUID) -> UUID:
        child = next(c for n, _, c in self.nodes(run_id) if n == "a")
        assert child is not None
        return child

    def event_seqs(self, run_id: UUID) -> list[int]:
        entries = stream_entries(self.redis, f"aether:workflow_runs:{run_id}:events")
        return [json.loads(fields["data"])["seq"] for _, fields in entries]


@pytest.fixture
def env(
    admin_connection_factory: _Factory,
    data_connection_factory: _Factory,
    redis_client: Redis,
) -> _Env:
    return _Env(data_connection_factory, admin_connection_factory, redis_client)


# --- R-6 --------------------------------------------------------------------------


def test_r6_parked_run_is_resumed_by_another_owner_and_reaches_end(env: _Env) -> None:
    """R-6: 파킹까지 간 뒤 프로세스가 바뀌어도(다른 owner·새 인스턴스) 자식 종결 뒤 이어서 END 에
    닿는다. 노드 실행 기록은 노드당 1행이고 `a` 의 자식 id 는 처음 영속한 그대로다."""
    run_id, _ = env.declare(input={"q": "hi"})

    parked = env.advance_as("worker-a")(run_id)

    assert parked is WorkflowRunStatus.WAITING_RUN
    status, waiting, lease_owner, lease_until = env.execution(run_id)
    child = env.child_of(run_id)
    assert (status, waiting, lease_owner, lease_until) == ("waiting_run", child, None, None)
    assert env.nodes(run_id) == [
        ("start", "succeeded", None),
        ("a", "waiting_run", child),
    ]
    (launch,) = env.launches()
    assert launch == {
        "agent_run_id": str(child),
        "agent_version_id": str(env.agent_version_id),
        "input": '{"q":"hi"}',
        "requested_by": str(env.key),
        "traceparent": "",
    }

    env.finish_child(child, "succeeded")
    finished = env.advance_as("worker-b-after-restart")(run_id)

    assert finished is WorkflowRunStatus.SUCCEEDED
    assert env.nodes(run_id) == [
        ("start", "succeeded", None),
        ("a", "succeeded", child),
        ("end", "succeeded", None),
    ]
    assert env.execution(run_id)[:2] == ("succeeded", None)
    assert len(env.launches()) == 1, "재개가 자식을 다시 발사하지 않는다"
    seqs = env.event_seqs(run_id)
    assert seqs == sorted(set(seqs)) and seqs[0] == 1, "seq 는 한 수열로 이어진다"


def test_r6_a_failed_child_ends_the_workflow_with_agent_run_failed(env: _Env) -> None:
    run_id, _ = env.declare()
    env.advance_as("worker-a")(run_id)
    env.finish_child(env.child_of(run_id), "timed_out")

    status = env.advance_as("worker-b")(run_id)

    assert status is WorkflowRunStatus.FAILED
    assert env.execution(run_id)[:2] == ("failed", None)
    assert [(n, s) for n, s, _ in env.nodes(run_id)] == [("start", "succeeded"), ("a", "failed")]


# --- R-7 --------------------------------------------------------------------------


def test_r7_parked_workflows_hold_no_lease_and_a_plain_agent_run_still_runs(
    env: _Env,
    admin_connection_factory: _Factory,
    db_host_port: tuple[str, int],
    redis_client: Redis,
) -> None:
    """R-7: 파킹된 Workflow Run 이 worker 슬롯을 점유하지 않는다 -- (a) 그 Run 들의 lease 열이
    비어 있고 (b) 실제 worker(`serve()`)가 평범한 Agent Run 을 정상 처리한다. 파킹된 수(6)가
    worker 의 소비 스레드 수보다 많다."""
    parked_ids = []
    for _ in range(6):
        run_id, _version = env.declare()
        assert env.advance_as("worker-a")(run_id) is WorkflowRunStatus.WAITING_RUN
        parked_ids.append(run_id)
    for run_id in parked_ids:
        status, _waiting, lease_owner, lease_until = env.execution(run_id)
        assert (status, lease_owner, lease_until) == ("waiting_run", None, None)

    host, port = db_host_port
    settings = Settings(
        database_url=f"postgresql+psycopg://{DATA_ROLE}:{DATA_PASSWORD}@{host}:{port}/aether",
        worker_consumer=f"test-r7-{uuid4()}",
        worker_heartbeat_seconds=1,
    )
    stop = threading.Event()
    ready = threading.Event()
    thread = threading.Thread(
        target=lambda: serve(
            settings, stop=stop, make_client=lambda: redis_client, on_ready=ready.set
        ),
        daemon=True,
    )
    thread.start()
    try:
        assert ready.wait(5.0), "worker 가 준비되지 않았습니다"
        plain_run = uuid4()
        conn = admin_connection_factory()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO control.runs (id, agent_version_id, input) VALUES (%s, %s, 'hi')",
                    (plain_run, env.agent_version_id),
                )
            conn.commit()
        finally:
            conn.close()
        redis_client.xadd(
            settings.worker_stream,
            {
                "run_id": str(plain_run),
                "agent_version_id": str(env.agent_version_id),
                "traceparent": "",
            },
        )

        def _plain_status() -> str | None:
            c = admin_connection_factory()
            try:
                with c.cursor() as cur:
                    cur.execute(
                        "SELECT status::text FROM data.run_executions WHERE run_id = %s",
                        (plain_run,),
                    )
                    row = cur.fetchone()
            finally:
                c.close()
            return None if row is None else str(row[0])

        assert wait_until(lambda: _plain_status() == "succeeded", timeout=15.0), (
            "파킹된 Workflow 가 있어도 평범한 Agent Run 이 처리되어야 한다"
        )
    finally:
        stop.set()
        thread.join(10.0)

    for run_id in parked_ids:
        assert env.execution(run_id)[2:] == (None, None), "대기 내내 lease 를 쥐지 않는다"


# --- R-8 --------------------------------------------------------------------------


def test_r8_the_same_request_twice_launches_one_child_and_records_one_row_per_node(
    env: _Env,
) -> None:
    """R-8: 같은 요청 메시지가 두 번 와도 자식 발사 1건, 노드 실행 기록 노드당 1행, 이벤트 증가
    없음."""
    run_id, version_id = env.declare()
    env.request(run_id, version_id)
    env.request(run_id, version_id)

    handled = env.drain_requests("worker-a")

    assert len(handled) == 2
    assert env.execution(run_id)[0] == "waiting_run"
    assert len(env.launches()) == 1
    assert [(n, s) for n, s, _ in env.nodes(run_id)] == [
        ("start", "succeeded"),
        ("a", "waiting_run"),
    ]
    assert env.event_seqs(run_id) == [1, 2, 3, 4, 5], "두 번째 요청이 이벤트를 더하지 않는다"


def test_r8_wake_by_both_paths_advances_the_node_once(env: _Env) -> None:
    """R-8: 빠른 경로(`on_agent_run_finished`)와 스위퍼(`sweep`)가 **둘 다** 같은 Workflow 를
    재큐해도
    노드는 한 번만 전진한다. 자식 발사 1건, 노드 실행 기록 노드당 1행, 종결 상태 하나."""
    run_id, _ = env.declare()
    env.advance_as("worker-a")(run_id)
    child = env.child_of(run_id)
    env.finish_child(child, "succeeded")
    resume = env.resume()

    fast = resume.on_agent_run_finished(child)
    swept = resume.sweep()
    handled = env.drain_requests("worker-b")

    assert (fast, swept) == (1, 1)
    assert [m.workflow_run_id for m in handled] == [run_id, run_id]
    assert env.execution(run_id)[:2] == ("succeeded", None)
    assert env.nodes(run_id) == [
        ("start", "succeeded", None),
        ("a", "succeeded", child),
        ("end", "succeeded", None),
    ]
    assert len(env.launches()) == 1
    seqs = env.event_seqs(run_id)
    assert seqs == list(range(1, len(seqs) + 1)), (
        "두 번째 재큐가 seq 에 빈틈도 중복도 만들지 않는다"
    )
    assert resume.sweep() == 0, "끝난 Workflow 는 더 이상 줍지 않는다"


# --- 스위퍼만으로 재개 --------------------------------------------------------------


def test_the_sweeper_alone_resumes_a_workflow_when_no_notification_ever_arrived(
    env: _Env,
) -> None:
    """spec 2.5 "이벤트만 믿지 않는다": 종결 통지(`aether:runs:status`)가 **한 건도 없고** 빠른 경로
    소비자도 없다 -- `sweep_once()` 만으로 파킹된 Workflow 가 END 에 닿는다. 자식이 아직 종결이
    아니면
    줍지 않는다."""
    run_id, _ = env.declare()
    env.advance_as("worker-a")(run_id)
    child = env.child_of(run_id)
    sweeper = WorkflowSweeper(env.resume(), interval_seconds=3600.0)

    env.finish_child(child, "running")
    assert sweeper.sweep_once() == 0, "자식이 아직 종결이 아니면 재큐하지 않는다"
    assert env.drain_requests("worker-b") == []
    assert env.execution(run_id)[0] == "waiting_run"

    env.finish_child(child, "succeeded")
    assert env.redis.xlen("aether:runs:status") == 0, "통지는 한 건도 없다"
    assert sweeper.sweep_once() == 1
    env.drain_requests("worker-b")

    assert env.execution(run_id)[:2] == ("succeeded", None)
    assert [(n, s) for n, s, _ in env.nodes(run_id)] == [
        ("start", "succeeded"),
        ("a", "succeeded"),
        ("end", "succeeded"),
    ]
    assert uuid.UUID(str(env.child_of(run_id))) == child
