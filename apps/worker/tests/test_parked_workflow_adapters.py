"""spec 0005 2.5 개정 3, R-7, R-8 (P4-2a B2): `PostgresParkedWorkflowFinder` 와
`RedisWorkflowRequeuer`
-- 실제 PostgreSQL(`aether_data` 역할)과 실제 Redis.

스위퍼의 판정 SQL 이 이 파일에서 갈립니다: `waiting_run` 이고 **자식이 이미 종결**인 것만 줍는다.
자식이 아직 종결이 아니거나(running·queued·waiting), 자식의 실행 행이 아직 없거나, Workflow 가
`waiting_run` 이 아니면 줍지 않는다. 빠른 경로(`waiting_on`)는 `waiting_run_id` 로 찾는다.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable

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
