"""spec 0005 2.5 개정 3, R-7, R-8 (P4-2a B2): `PostgresParkedWorkflowFinder` 와
`RedisWorkflowRequeuer`
-- 실제 PostgreSQL(`aether_data` 역할)과 실제 Redis.

스위퍼의 판정 SQL 이 이 파일에서 갈립니다: `waiting_run` 이고 **자식이 이미 종결**인 것만 줍는다.
자식이 아직 종결이 아니거나(running·queued·waiting), 자식의 실행 행이 아직 없거나, Workflow 가
`waiting_run` 이 아니면 줍지 않는다. 빠른 경로(`waiting_on`)는 `waiting_run_id` 로 찾는다.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable, Iterator

import psycopg
import pytest
from aether_worker.adapters.outbound.db.parked_workflow_finder import PostgresParkedWorkflowFinder
from aether_worker.adapters.outbound.redis.workflow_requeuer import RedisWorkflowRequeuer
from aether_worker.application.ports.outbound.parked_workflow_finder import ParkedWorkflow
from aether_workflow.domain.node import Edge, Node, NodeKind
from redis import Redis

from tests.support.redis import stream_entries
from tests.support.workflow_db import declare_workflow_run

pytestmark = pytest.mark.integration

_Factory = Callable[[], psycopg.Connection]
_TERMINAL = ("succeeded", "failed", "cancelled", "timed_out")
_NOT_TERMINAL = ("queued", "running", "waiting")


def _child(admin: _Factory, status: str | None) -> uuid.UUID:
    """`control.runs` 선언 하나와, `status` 가 주어지면 `data.run_executions` 행 하나."""
    conn = admin()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO control.agents (name, current_version) VALUES (%s, 1) RETURNING id",
                (f"child-{uuid.uuid4()}",),
            )
            row = cur.fetchone()
            assert row is not None
            cur.execute(
                "INSERT INTO control.agent_versions (agent_id, version, definition)"
                " VALUES (%s, 1, '{\"schema_version\": 1}') RETURNING id",
                (row[0],),
            )
            version = cur.fetchone()
            assert version is not None
            run_id = uuid.uuid4()
            cur.execute(
                "INSERT INTO control.runs (id, agent_version_id, input) VALUES (%s, %s, 'x')",
                (run_id, version[0]),
            )
            if status is not None:
                cur.execute(
                    "INSERT INTO data.run_executions (run_id, status) VALUES (%s, %s)",
                    (run_id, status),
                )
        conn.commit()
    finally:
        conn.close()
    return run_id


def _parked(admin: _Factory, workflow_status: str, child: uuid.UUID | None) -> ParkedWorkflow:
    run_id, version_id = declare_workflow_run(
        admin,
        (Node("s", NodeKind.START), Node("e", NodeKind.END)),
        (Edge("s", "e"),),
    )
    conn = admin()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO data.workflow_run_executions (workflow_run_id, status, waiting_run_id)"
                " VALUES (%s, %s::control.workflow_run_status, %s)",
                (run_id, workflow_status, child),
            )
        conn.commit()
    finally:
        conn.close()
    return ParkedWorkflow(workflow_run_id=run_id, workflow_version_id=version_id)


@pytest.mark.parametrize("child_status", _TERMINAL)
def test_a_parked_workflow_whose_child_is_terminal_is_ready(
    child_status: str, admin_connection_factory: _Factory, data_connection_factory: _Factory
) -> None:
    child = _child(admin_connection_factory, child_status)
    parked = _parked(admin_connection_factory, "waiting_run", child)

    ready = PostgresParkedWorkflowFinder(data_connection_factory).ready_to_resume()

    assert parked in ready


@pytest.mark.parametrize("child_status", _NOT_TERMINAL)
def test_a_parked_workflow_whose_child_is_not_terminal_is_not_ready(
    child_status: str, admin_connection_factory: _Factory, data_connection_factory: _Factory
) -> None:
    """자식이 아직 종결이 아니면 줍지 않는다 -- 줍는다고 틀리지는 않지만(실행기가 멱등) 매 주기마다
    불필요한 재큐가 쌓인다."""
    child = _child(admin_connection_factory, child_status)
    parked = _parked(admin_connection_factory, "waiting_run", child)

    assert parked not in PostgresParkedWorkflowFinder(data_connection_factory).ready_to_resume()


def test_a_child_nobody_has_picked_up_yet_is_not_ready(
    admin_connection_factory: _Factory, data_connection_factory: _Factory
) -> None:
    """자식 Run 의 실행 행이 아직 없다(worker 가 집지 않음) -- 종결이 아니다."""
    child = _child(admin_connection_factory, None)
    parked = _parked(admin_connection_factory, "waiting_run", child)

    assert parked not in PostgresParkedWorkflowFinder(data_connection_factory).ready_to_resume()


@pytest.mark.parametrize("workflow_status", ["queued", "running", "succeeded", "failed"])
def test_a_workflow_that_is_not_parked_is_never_ready(
    workflow_status: str, admin_connection_factory: _Factory, data_connection_factory: _Factory
) -> None:
    child = _child(admin_connection_factory, "succeeded")
    parked = _parked(admin_connection_factory, workflow_status, child)

    assert parked not in PostgresParkedWorkflowFinder(data_connection_factory).ready_to_resume()


def test_waiting_on_finds_the_workflow_parked_on_that_child_only(
    admin_connection_factory: _Factory, data_connection_factory: _Factory
) -> None:
    child, other = (
        _child(admin_connection_factory, "succeeded"),
        _child(admin_connection_factory, "succeeded"),
    )
    parked = _parked(admin_connection_factory, "waiting_run", child)
    _parked(admin_connection_factory, "waiting_run", other)
    _parked(admin_connection_factory, "running", child)  # 파킹이 아니다
    finder = PostgresParkedWorkflowFinder(data_connection_factory)

    assert finder.waiting_on(child) == (parked,)
    assert finder.waiting_on(uuid.uuid4()) == ()


def test_requeue_writes_the_workflow_request_contract(redis_client: Redis) -> None:
    """A 의 요청 스트림 계약 그대로 -- `aether:workflow_runs:requested` 에 `workflow_run_id`·
    `workflow_version_id`·`traceparent`(빈 문자열)."""
    parked = ParkedWorkflow(workflow_run_id=uuid.uuid4(), workflow_version_id=uuid.uuid4())

    RedisWorkflowRequeuer(redis_client).requeue(parked)

    entries = stream_entries(redis_client, "aether:workflow_runs:requested")
    assert [fields for _, fields in entries] == [
        {
            "workflow_run_id": str(parked.workflow_run_id),
            "workflow_version_id": str(parked.workflow_version_id),
            "traceparent": "",
        }
    ]


# --- P4-4: 승인 대기를 스위퍼가 줍는다 ---------------------------------------------------


def _waiting_approval(
    admin: _Factory, awaited: uuid.UUID | None, *, approved: list[uuid.UUID]
) -> ParkedWorkflow:
    """`waiting_approval` Workflow Run 하나. `approved` 의 각 노드 실행 id 에 승인 기록을 심는다."""
    run_id, version_id = declare_workflow_run(
        admin,
        (Node("s", NodeKind.START), Node("e", NodeKind.END)),
        (Edge("s", "e"),),
    )
    conn = admin()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO data.workflow_run_executions"
                " (workflow_run_id, status, waiting_node_execution_id)"
                " VALUES (%s, 'waiting_approval'::control.workflow_run_status, %s)",
                (run_id, awaited),
            )
            for node_execution_id in approved:
                cur.execute(
                    "INSERT INTO control.workflow_approvals"
                    " (workflow_run_id, node_execution_id, approved_by) VALUES (%s, %s, 'tester')",
                    (run_id, node_execution_id),
                )
        conn.commit()
    finally:
        conn.close()
    return ParkedWorkflow(workflow_run_id=run_id, workflow_version_id=version_id)


def test_a_workflow_waiting_for_approval_that_has_been_approved_is_ready(
    admin_connection_factory: _Factory, data_connection_factory: _Factory
) -> None:
    """spec 0005 2.5 (P4-4): 승인 뒤 재큐가 유실돼도 영원히 멈추지 않는다 -- 승인이 **이미 저장된**
    `waiting_approval` 은 스위퍼가 줍는다(이벤트만 믿지 않는다, `2026-10-11-001`)."""
    awaited = uuid.uuid4()
    parked = _waiting_approval(admin_connection_factory, awaited, approved=[awaited])

    assert parked in PostgresParkedWorkflowFinder(data_connection_factory).ready_to_resume()


def test_a_workflow_still_waiting_for_its_approval_is_not_ready(
    admin_connection_factory: _Factory, data_connection_factory: _Factory
) -> None:
    """승인이 없는 대기는 줍지 않는다 -- 줍는다고 틀리지는 않지만(실행기가 승인을 확인) 승인 전에는
    매 주기마다 쓸데없는 재큐가 쌓인다."""
    parked = _waiting_approval(admin_connection_factory, uuid.uuid4(), approved=[])

    assert parked not in PostgresParkedWorkflowFinder(data_connection_factory).ready_to_resume()


def test_an_approval_for_another_node_execution_does_not_make_the_wait_ready(
    admin_connection_factory: _Factory, data_connection_factory: _Factory
) -> None:
    """R-12: 기다리는 그 노드 실행의 승인만 근거다."""
    parked = _waiting_approval(admin_connection_factory, uuid.uuid4(), approved=[uuid.uuid4()])

    assert parked not in PostgresParkedWorkflowFinder(data_connection_factory).ready_to_resume()


def test_a_waiting_approval_without_a_pointer_is_never_ready(
    admin_connection_factory: _Factory, data_connection_factory: _Factory
) -> None:
    """fail-closed: 지목 대상이 비어 있으면 어떤 승인도 근거가 되지 못한다."""
    parked = _waiting_approval(admin_connection_factory, None, approved=[uuid.uuid4()])

    assert parked not in PostgresParkedWorkflowFinder(data_connection_factory).ready_to_resume()


def test_the_approval_branch_does_not_disturb_the_child_run_branch(
    admin_connection_factory: _Factory, data_connection_factory: _Factory
) -> None:
    """회귀(R-13): 한 번의 조회가 두 대기를 함께 줍는다 -- 자식이 종결인 `waiting_run` 과 승인이
    있는
    `waiting_approval` 이 같이 나오고, 각자 한 번씩만 나온다."""
    awaited = uuid.uuid4()
    waiting_run = _parked(
        admin_connection_factory, "waiting_run", _child(admin_connection_factory, "failed")
    )
    waiting_approval = _waiting_approval(admin_connection_factory, awaited, approved=[awaited])

    ready = PostgresParkedWorkflowFinder(data_connection_factory).ready_to_resume()

    assert ready.count(waiting_run) == 1
    assert ready.count(waiting_approval) == 1


# --- P4-3: 타이머 대기는 스위퍼가 주 경로다 -----------------------------------------------


def _waiting_timer(admin: _Factory, wake_at_sql: str) -> ParkedWorkflow:
    """`waiting_timer` Workflow Run 하나. `wake_at_sql` 은 `now()` 기준 SQL 식(`NULL` 포함)이다."""
    run_id, version_id = declare_workflow_run(
        admin,
        (Node("s", NodeKind.START), Node("e", NodeKind.END)),
        (Edge("s", "e"),),
    )
    conn = admin()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO data.workflow_run_executions (workflow_run_id, status, wake_at)"
                f" VALUES (%s, 'waiting_timer'::control.workflow_run_status, {wake_at_sql})",
                (run_id,),
            )
        conn.commit()
    finally:
        conn.close()
    return ParkedWorkflow(workflow_run_id=run_id, workflow_version_id=version_id)


@pytest.fixture
def timer_waits(admin_connection_factory: _Factory) -> Iterator[Callable[[str], ParkedWorkflow]]:
    """`waiting_timer` Run 을 만들고, 테스트가 끝나면 `cancelled` 로 치운다 - DB 는 세션 안에서
    공유되고 `wake_at` 이 지난 `waiting_timer` 는 다른 테스트의 `sweep()` 이 줍기 때문이다."""
    created: list[ParkedWorkflow] = []

    def make(wake_at_sql: str) -> ParkedWorkflow:
        parked = _waiting_timer(admin_connection_factory, wake_at_sql)
        created.append(parked)
        return parked

    yield make

    conn = admin_connection_factory()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE data.workflow_run_executions SET status = 'cancelled'"
                " WHERE workflow_run_id = ANY(%s)",
                ([p.workflow_run_id for p in created],),
            )
        conn.commit()
    finally:
        conn.close()


def test_a_timer_wait_whose_wake_time_has_passed_is_ready(
    timer_waits: Callable[[str], ParkedWorkflow], data_connection_factory: _Factory
) -> None:
    """spec 0005 2.7 개정 7 (5): `WAIT` 에는 깨우는 외부 사건이 없다 - `wake_at <= now()` 인
    `waiting_timer` 를 스위퍼가 줍는다(안전망이 아니라 주 경로)."""
    parked = timer_waits("now() - interval '1 minute'")

    assert parked in PostgresParkedWorkflowFinder(data_connection_factory).ready_to_resume()


def test_a_timer_wait_whose_wake_time_has_not_come_is_not_ready(
    timer_waits: Callable[[str], ParkedWorkflow], data_connection_factory: _Factory
) -> None:
    """아직이면 줍지 않는다 - 줍으면 매 주기마다 실행기가 헛되이 깨어난다."""
    parked = timer_waits("now() + interval '1 day'")

    assert parked not in PostgresParkedWorkflowFinder(data_connection_factory).ready_to_resume()


def test_a_timer_wait_without_a_wake_time_is_never_ready(
    timer_waits: Callable[[str], ParkedWorkflow], data_connection_factory: _Factory
) -> None:
    """fail-closed: 깨어날 시각이 비어 있으면 근거가 없다(`NULL <= now()` 는 참이 아니다)."""
    parked = timer_waits("NULL")

    assert parked not in PostgresParkedWorkflowFinder(data_connection_factory).ready_to_resume()


def test_the_timer_branch_does_not_disturb_the_other_two_branches(
    admin_connection_factory: _Factory,
    timer_waits: Callable[[str], ParkedWorkflow],
    data_connection_factory: _Factory,
) -> None:
    """회귀(R-13): 한 번의 조회가 세 대기를 함께 줍는다 - 각자 한 번씩만 나온다."""
    awaited = uuid.uuid4()
    waiting_run = _parked(
        admin_connection_factory, "waiting_run", _child(admin_connection_factory, "failed")
    )
    waiting_approval = _waiting_approval(admin_connection_factory, awaited, approved=[awaited])
    waiting_timer = timer_waits("now() - interval '1 second'")

    ready = PostgresParkedWorkflowFinder(data_connection_factory).ready_to_resume()

    assert ready.count(waiting_run) == 1
    assert ready.count(waiting_approval) == 1
    assert ready.count(waiting_timer) == 1
