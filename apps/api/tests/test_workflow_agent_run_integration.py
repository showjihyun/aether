"""spec 0005 2.2 개정 3, 2.5 개정 3 (P4-2a B1): 노드의 Agent 참조와 자식 Agent Run 선언 -- 실제
PostgreSQL + Redis.

`api-integration`. 증명하는 것:

1. `agent_id`·`agent_version` 이 저장과 읽기를 왕복한다.
2. **두 키가 없는 기존 행**(P4-1·A 가 만든 Version)을 읽어도 `KeyError` 로 터지지 않는다.
3. `create_with_id` 를 같은 id 로 두 번 부르면 `control.runs` 행은 1건이고 두 번째는 `False`,
   `requested_by` 는 비어 있다.
4. 소비자 왕복: 스트림 메시지 -> 선언 1건 + `aether:runs:requested` 통지 1건. 같은 메시지가
   두 번 와도 선언 1건 / 통지 1건.
5. 없는 `agent_version_id`(FK 위반)는 소비자가 삼키지 않고 올리며 PEL 에 남긴다.
"""

from __future__ import annotations

import json
import threading
import uuid
from collections.abc import Callable
from typing import Any

import psycopg
import pytest
from aether_api.adapters.inbound.stream.status_consumer import ensure_group
from aether_api.adapters.inbound.stream.workflow_agent_run_consumer import (
    WorkflowAgentRunConsumer,
)
from aether_api.adapters.outbound.db.agent_repository import PostgresAgentRepository
from aether_api.adapters.outbound.db.api_keys import PostgresApiKeyStore
from aether_api.adapters.outbound.db.run_declaration_store import PostgresRunDeclarationStore
from aether_api.adapters.outbound.redis.run_notifier import RedisRunNotifier
from aether_api.application.usecases.declare_workflow_agent_run import (
    DeclareWorkflowAgentRunUseCase,
)
from aether_api.application.usecases.issue_api_key import IssueApiKeyUseCase
from aether_api.domain.workflow_agent_run_request import WorkflowAgentRunRequest
from aether_api.main import create_app
from aether_api.settings import Settings
from aether_runtime.domain.agent import AgentDefinition
from fastapi.testclient import TestClient
from redis import Redis

from tests.support.waiting import wait_until

pytestmark = pytest.mark.integration

_Factory = Callable[[], psycopg.Connection]
_REQUESTS = "aether:workflow:agent_runs:requested"
_RUNS_REQUESTED = "aether:runs:requested"
_GROUP = "aether-api"
_JOIN_TIMEOUT = 5.0


def _xrange_all(client: Redis, stream: str) -> list[tuple[str, dict[str, str]]]:
    entries = client.xrange(stream, min="-", max="+")
    assert entries is not None
    result: list[tuple[str, dict[str, str]]] = []
    for entry_id, fields in entries:
        assert isinstance(entry_id, str)
        assert fields is not None
        narrowed: dict[str, str] = {}
        for key, value in fields.items():
            assert isinstance(key, str)
            assert isinstance(value, str)
            narrowed[key] = value
        result.append((entry_id, narrowed))
    return result


def _agent_version_id(connect: _Factory) -> uuid.UUID:
    repo = PostgresAgentRepository(connect)
    definition = AgentDefinition.model_validate({"schema_version": 1, "system_prompt": "x"})
    agent = repo.create(f"wf-agent-run-{uuid.uuid4()}", definition)
    return repo.get_version(agent.id, 1).id


def _runs(admin: _Factory, run_id: uuid.UUID) -> list[tuple[Any, ...]]:
    conn = admin()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, agent_version_id, input, status::text, requested_by "
                "FROM control.runs WHERE id = %s",
                (run_id,),
            )
            return cur.fetchall()
    finally:
        conn.close()


# --- 1, 2: 정의 표면 ---------------------------------------------------------------


@pytest.fixture
def client(control_database_url: str) -> TestClient:
    return TestClient(create_app(Settings(database_url=control_database_url)))


@pytest.fixture
def auth_headers(control_connection_factory: _Factory) -> dict[str, str]:
    issued = IssueApiKeyUseCase(PostgresApiKeyStore(control_connection_factory))(
        f"test-wf-agent-node-{uuid.uuid4()}"
    )
    return {"Authorization": f"Bearer {issued.raw_key}"}


def test_agent_reference_round_trips_through_the_database(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    """`agent_id`·`agent_version` 이 jsonb 를 거쳐 그대로 돌아온다(POST 응답, GET, 버전별 GET)."""
    agent_id = str(uuid.uuid4())
    nodes = [
        {"id": "s", "kind": "START", "max_iterations": None},
        {"id": "a", "kind": "AGENT", "max_iterations": None, "agent_id": agent_id,
         "agent_version": 4},
        {"id": "b", "kind": "AGENT", "max_iterations": None, "agent_id": agent_id},
        {"id": "e", "kind": "END", "max_iterations": None},
    ]  # fmt: skip
    edges = [
        {"source": "s", "target": "a", "label": None},
        {"source": "a", "target": "b", "label": None},
        {"source": "b", "target": "e", "label": None},
    ]

    created = client.post(
        "/workflows", json={"name": f"wf-{uuid.uuid4()}", "nodes": nodes, "edges": edges},
        headers=auth_headers,
    )  # fmt: skip

    assert created.status_code == 201, created.text
    workflow_id = created.json()["id"]
    expected = {"s": (None, None), "a": (agent_id, 4), "b": (agent_id, None), "e": (None, None)}
    for body in (
        created.json(),
        client.get(f"/workflows/{workflow_id}", headers=auth_headers).json(),
        client.get(f"/workflows/{workflow_id}/versions/1", headers=auth_headers).json(),
    ):
        assert {n["id"]: (n["agent_id"], n["agent_version"]) for n in body["nodes"]} == expected


def test_rows_stored_before_the_agent_keys_existed_are_still_readable(
    client: TestClient,
    auth_headers: dict[str, str],
    admin_connection_factory: _Factory,
) -> None:
    """P4-1·A 가 만든 Version 의 `nodes` 에는 `agent_id`·`agent_version` 키가 **없다** -- 읽기가
    `KeyError`(500) 로 터지지 않고 두 값을 `None` 으로 돌려준다. 손으로 옛 모양을 INSERT 한다."""
    old_nodes = [
        {"id": "s", "kind": "START", "max_iterations": None},
        {"id": "e", "kind": "END", "max_iterations": None},
    ]
    old_edges = [{"source": "s", "target": "e", "label": None}]
    conn = admin_connection_factory()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO control.workflows (name) VALUES (%s) RETURNING id",
                (f"legacy-{uuid.uuid4()}",),
            )
            row = cur.fetchone()
            assert row is not None
            workflow_id = row[0]
            cur.execute(
                "INSERT INTO control.workflow_versions (workflow_id, version, nodes, edges) "
                "VALUES (%s, 1, %s, %s)",
                (workflow_id, json.dumps(old_nodes), json.dumps(old_edges)),
            )
        conn.commit()
    finally:
        conn.close()

    current = client.get(f"/workflows/{workflow_id}", headers=auth_headers)
    versioned = client.get(f"/workflows/{workflow_id}/versions/1", headers=auth_headers)

    assert current.status_code == 200, current.text
    assert versioned.status_code == 200, versioned.text
    for body in (current.json(), versioned.json()):
        assert [(n["id"], n["agent_id"], n["agent_version"]) for n in body["nodes"]] == [
            ("s", None, None),
            ("e", None, None),
        ]


# --- 3: create_with_id --------------------------------------------------------------


def test_create_with_id_twice_leaves_one_row_and_the_second_returns_false(
    control_connection_factory: _Factory, admin_connection_factory: _Factory
) -> None:
    store = PostgresRunDeclarationStore(control_connection_factory)
    version_id = _agent_version_id(control_connection_factory)
    key_id = IssueApiKeyUseCase(PostgresApiKeyStore(control_connection_factory))(
        f"k-{uuid.uuid4()}"
    ).key.id
    run_id = uuid.uuid4()

    first = store.create_with_id(run_id, version_id, "child input", key_id)
    second = store.create_with_id(run_id, version_id, "a different input", key_id)

    assert (first, second) == (True, False)
    rows = _runs(admin_connection_factory, run_id)
    assert len(rows) == 1
    _id, stored_version, stored_input, status, requested_by = rows[0]
    assert (stored_version, stored_input, status) == (version_id, "child input", "queued")
    assert requested_by == key_id  # Workflow 를 시작한 주체를 물려받는다(비우면 GET /runs 가 500)


def test_create_with_id_for_an_unknown_version_raises(
    control_connection_factory: _Factory, admin_connection_factory: _Factory
) -> None:
    """FK 위반은 삼키지 않는다 -- 버그를 조용히 만들지 않는다."""
    store = PostgresRunDeclarationStore(control_connection_factory)
    run_id = uuid.uuid4()

    with pytest.raises(psycopg.errors.ForeignKeyViolation):
        store.create_with_id(run_id, uuid.uuid4(), "x", None)

    assert _runs(admin_connection_factory, run_id) == []


# --- 4, 5: 소비자 왕복 ----------------------------------------------------------------


def _fields(run_id: uuid.UUID, version_id: uuid.UUID) -> dict[Any, Any]:
    return {
        "agent_run_id": str(run_id),
        "agent_version_id": str(version_id),
        "input": "child input",
        "traceparent": "00-abc-def-01",
    }


def test_redelivered_message_declares_one_run_and_notifies_the_still_queued_run_again(
    control_connection_factory: _Factory,
    admin_connection_factory: _Factory,
    redis_client: Redis,
) -> None:
    version_id = _agent_version_id(control_connection_factory)
    run_id = uuid.uuid4()
    ensure_group(redis_client, _REQUESTS, _GROUP)
    redis_client.xadd(_REQUESTS, _fields(run_id, version_id))
    redis_client.xadd(_REQUESTS, _fields(run_id, version_id))  # 같은 메시지 재전달

    use_case = DeclareWorkflowAgentRunUseCase(
        PostgresRunDeclarationStore(control_connection_factory), RedisRunNotifier(redis_client)
    )
    results: list[bool] = []

    def recording(request: WorkflowAgentRunRequest) -> bool:
        created = use_case(request)
        results.append(created)
        return created

    stop = threading.Event()
    consumer = WorkflowAgentRunConsumer(redis_client, recording, consumer="api-a", block_ms=200)
    thread = threading.Thread(target=consumer.run_until, args=(stop,))
    thread.start()
    try:
        drained = wait_until(
            lambda: len(results) == 2 and redis_client.xpending(_REQUESTS, _GROUP)["pending"] == 0,
            timeout=_JOIN_TIMEOUT,
        )
        assert drained, "5초 안에 두 메시지를 처리하지 못했습니다"
    finally:
        stop.set()
        thread.join(_JOIN_TIMEOUT)

    assert not thread.is_alive()
    assert results == [True, False]
    assert len(_runs(admin_connection_factory, run_id)) == 1, "선언은 한 행입니다(멱등)"
    notified = _xrange_all(redis_client, _RUNS_REQUESTED)
    # 2026-10-14 리뷰: 재전달이어도 자식 Run 이 아직 `queued` 면 다시 통지합니다 — 통지가
    # 유실된 채 `queued` 로 남으면 그것을 기다리는 Workflow 가 영원히 파킹됩니다.
    assert len(notified) == 2
    expected = {
        "run_id": str(run_id),
        "agent_version_id": str(version_id),
        "traceparent": "00-abc-def-01",
    }
    assert [fields for _id, fields in notified] == [expected, expected]


def test_a_run_already_picked_up_is_not_notified_again(
    control_connection_factory: _Factory,
    admin_connection_factory: _Factory,
    redis_client: Redis,
) -> None:
    """`running` 으로 올라간 자식 Run 은 재전달에도 통지하지 않는다(실제 상태 열로 판정)."""
    version_id = _agent_version_id(control_connection_factory)
    run_id = uuid.uuid4()
    use_case = DeclareWorkflowAgentRunUseCase(
        PostgresRunDeclarationStore(control_connection_factory), RedisRunNotifier(redis_client)
    )
    request = WorkflowAgentRunRequest(
        agent_run_id=run_id, agent_version_id=version_id, input="summarize", traceparent=""
    )

    assert use_case(request) is True

    admin = admin_connection_factory()
    try:
        with admin.cursor() as cur:
            cur.execute("UPDATE control.runs SET status = 'running' WHERE id = %s", (run_id,))
        admin.commit()
    finally:
        admin.close()

    assert use_case(request) is False
    assert len(_xrange_all(redis_client, _RUNS_REQUESTED)) == 1


def test_unknown_agent_version_is_raised_by_the_consumer_and_left_pending(
    control_connection_factory: _Factory,
    admin_connection_factory: _Factory,
    redis_client: Redis,
) -> None:
    """FK 위반(실행기가 걸러 냈어야 할 버그)은 ack 되지 않고 PEL 에 남으며 통지도 없다."""
    run_id = uuid.uuid4()
    ensure_group(redis_client, _REQUESTS, _GROUP)
    redis_client.xadd(_REQUESTS, _fields(run_id, uuid.uuid4()))
    use_case = DeclareWorkflowAgentRunUseCase(
        PostgresRunDeclarationStore(control_connection_factory), RedisRunNotifier(redis_client)
    )
    consumer = WorkflowAgentRunConsumer(redis_client, use_case, consumer="api-a", block_ms=200)

    with pytest.raises(psycopg.errors.ForeignKeyViolation):
        consumer.run_until(threading.Event())

    assert redis_client.xpending(_REQUESTS, _GROUP)["pending"] == 1
    assert _runs(admin_connection_factory, run_id) == []
    assert _xrange_all(redis_client, _RUNS_REQUESTED) == []
