"""spec 0005 2.2, 2.3, 2.9 개정 2, R-13 (P4-2a A1): Workflow Run API 와 두 스트림 — 실제
PostgreSQL + Redis + 실제 인증.

`api-integration`. `POST /workflows/{id}/runs` 202 와 `control.workflow_runs` 행·
`aether:workflow_runs:requested` 메시지(Agent Run 의 `aether:runs:requested` 와 **다른 스트림**),
`RedisWorkflowRunNotifier` 의 필드 계약, 투영 소비자 왕복(`aether:workflow_runs:status` →
`GET /workflow-runs/{id}`).
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from typing import Any
from uuid import UUID, uuid4

import psycopg
import pytest
from aether_api.adapters.inbound.stream.status_consumer import ensure_group
from aether_api.adapters.inbound.stream.workflow_run_status_consumer import (
    WorkflowRunStatusConsumer,
)
from aether_api.adapters.outbound.db.api_keys import PostgresApiKeyStore
from aether_api.adapters.outbound.db.workflow_run_declaration_store import (
    PostgresWorkflowRunDeclarationStore,
)
from aether_api.adapters.outbound.redis.workflow_run_notifier import RedisWorkflowRunNotifier
from aether_api.application.usecases.apply_workflow_run_status import (
    ApplyWorkflowRunStatusUseCase,
)
from aether_api.application.usecases.issue_api_key import IssueApiKeyUseCase
from aether_api.domain.workflow_run_status_message import WorkflowRunStatusMessage
from aether_api.main import create_app
from aether_api.settings import Settings
from fastapi.testclient import TestClient
from redis import Redis

from tests.support.waiting import wait_until

pytestmark = pytest.mark.integration

_REQUESTED = "aether:workflow_runs:requested"
_STATUS = "aether:workflow_runs:status"
_AGENT_RUNS_REQUESTED = "aether:runs:requested"
_GROUP = "aether-api"
_JOIN_TIMEOUT = 5.0


def _xrange_all(client: Redis, stream: str) -> list[tuple[str, dict[str, str]]]:
    """redis-py 스텁이 허용하는 `None`/`bytes` 를 좁힙니다(`test_run_notifier.py` 와 같은 헬퍼)."""
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


# --- RedisWorkflowRunNotifier -----------------------------------------------------


def test_notifier_writes_the_three_contract_fields(redis_client: Redis) -> None:
    """plan 부록 A: `aether:workflow_runs:requested` 에 `workflow_run_id`·`workflow_version_id`·
    `traceparent` 를 XADD 한다."""
    run_id, version_id = uuid4(), uuid4()

    RedisWorkflowRunNotifier(redis_client).requested(run_id, version_id, "00-trace-01")

    entries = _xrange_all(redis_client, _REQUESTED)
    assert len(entries) == 1
    assert entries[0][1] == {
        "workflow_run_id": str(run_id),
        "workflow_version_id": str(version_id),
        "traceparent": "00-trace-01",
    }
    assert _xrange_all(redis_client, _AGENT_RUNS_REQUESTED) == []


def test_notifier_sends_empty_traceparent_when_none(redis_client: Redis) -> None:
    RedisWorkflowRunNotifier(redis_client).requested(uuid4(), uuid4(), None)

    _id, fields = _xrange_all(redis_client, _REQUESTED)[0]
    assert fields["traceparent"] == ""


# --- API ---------------------------------------------------------------------------


@pytest.fixture
def client(control_database_url: str, redis_url: str) -> TestClient:
    return TestClient(create_app(Settings(database_url=control_database_url, redis_url=redis_url)))


@pytest.fixture
def auth_headers(control_connection_factory: Callable[[], psycopg.Connection]) -> dict[str, str]:
    issued = IssueApiKeyUseCase(PostgresApiKeyStore(control_connection_factory))(
        f"test-workflow-runs-{uuid4()}"
    )
    return {"Authorization": f"Bearer {issued.raw_key}"}


def _node(node_id: str, kind: str) -> dict[str, Any]:
    return {"id": node_id, "kind": kind, "max_iterations": None}


def _create_workflow(client: TestClient, headers: dict[str, str]) -> str:
    response = client.post(
        "/workflows",
        json={
            "name": f"wf-{uuid4()}",
            "nodes": [_node("s", "START"), _node("e", "END")],
            "edges": [{"source": "s", "target": "e", "label": None}],
        },
        headers=headers,
    )
    assert response.status_code == 201, response.text
    workflow_id: str = response.json()["id"]
    return workflow_id


def test_post_run_declares_notifies_and_get_reads_the_projection(
    client: TestClient,
    auth_headers: dict[str, str],
    redis_client: Redis,
    admin_connection_factory: Callable[[], psycopg.Connection],
) -> None:
    workflow_id = _create_workflow(client, auth_headers)

    response = client.post(
        f"/workflows/{workflow_id}/runs", json={"input": {"q": "hi"}}, headers=auth_headers
    )

    assert response.status_code == 202, response.text
    body = response.json()
    assert set(body) == {
        "workflow_run_id",
        "workflow_id",
        "workflow_version",
        "status",
        "requested_at",
    }
    assert body["status"] == "queued"
    assert body["workflow_version"] == 1

    admin = admin_connection_factory()
    try:
        with admin.cursor() as cur:
            cur.execute(
                "SELECT input, status::text, status_seq, workflow_version_id "
                "FROM control.workflow_runs WHERE id = %s",
                (body["workflow_run_id"],),
            )
            row = cur.fetchone()
    finally:
        admin.close()
    assert row is not None
    assert row[:3] == ({"q": "hi"}, "queued", 0)

    entries = _xrange_all(redis_client, _REQUESTED)
    assert len(entries) == 1
    assert entries[0][1]["workflow_run_id"] == body["workflow_run_id"]
    assert entries[0][1]["workflow_version_id"] == str(row[3])
    assert "traceparent" in entries[0][1]
    assert _xrange_all(redis_client, _AGENT_RUNS_REQUESTED) == []

    detail = client.get(f"/workflow-runs/{body['workflow_run_id']}", headers=auth_headers)
    assert detail.status_code == 200, detail.text
    assert detail.json()["status"] == "queued"
    assert detail.json()["workflow_version_id"] == str(row[3])


def test_post_run_404s_distinguish_workflow_and_version(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    workflow_id = _create_workflow(client, auth_headers)

    missing_workflow = client.post(
        f"/workflows/{uuid4()}/runs", json={"input": None}, headers=auth_headers
    )
    missing_version = client.post(
        f"/workflows/{workflow_id}/runs",
        json={"input": None, "workflow_version": 7},
        headers=auth_headers,
    )
    missing_run = client.get(f"/workflow-runs/{uuid4()}", headers=auth_headers)

    assert missing_workflow.json() == {"detail": "workflow_not_found"}
    assert missing_version.json() == {"detail": "workflow_version_not_found"}
    assert missing_run.json() == {"detail": "workflow_run_not_found"}
    assert {missing_workflow.status_code, missing_version.status_code, missing_run.status_code} == {
        404
    }


def test_status_stream_message_is_projected_by_the_consumer(
    client: TestClient,
    auth_headers: dict[str, str],
    redis_client: Redis,
    control_connection_factory: Callable[[], psycopg.Connection],
) -> None:
    """상태 스트림 → 소비자 → 저장소 → `GET`. 낮은 `seq` 가 늦게 와도 결과가 바뀌지 않는다."""
    workflow_id = _create_workflow(client, auth_headers)
    run_id = client.post(
        f"/workflows/{workflow_id}/runs", json={"input": None}, headers=auth_headers
    ).json()["workflow_run_id"]

    ensure_group(redis_client, _STATUS, _GROUP)
    redis_client.xadd(
        _STATUS,
        {
            "workflow_run_id": run_id,
            "seq": "2",
            "status": "succeeded",
            "at": "2026-01-01T00:00:02+00:00",
            "current_node_id": "e",
            "started_at": "2026-01-01T00:00:01+00:00",
            "finished_at": "2026-01-01T00:00:02+00:00",
        },
    )
    redis_client.xadd(
        _STATUS,
        {
            "workflow_run_id": run_id,
            "seq": "1",
            "status": "running",
            "at": "2026-01-01T00:00:01+00:00",
        },
    )
    stop = threading.Event()
    apply = ApplyWorkflowRunStatusUseCase(
        PostgresWorkflowRunDeclarationStore(control_connection_factory)
    )
    results: list[bool] = []

    def recording_apply(message: WorkflowRunStatusMessage) -> bool:
        applied = apply(message)
        results.append(applied)
        return applied

    consumer = WorkflowRunStatusConsumer(
        redis_client, recording_apply, consumer="api-a", block_ms=200
    )
    thread = threading.Thread(target=consumer.run_until, args=(stop,))
    thread.start()
    try:
        drained = wait_until(
            lambda: len(results) == 2 and redis_client.xpending(_STATUS, _GROUP)["pending"] == 0,
            timeout=_JOIN_TIMEOUT,
        )
        assert drained, "5초 안에 두 메시지를 처리하지 못했습니다"
    finally:
        stop.set()
        thread.join(_JOIN_TIMEOUT)

    assert not thread.is_alive()
    assert results == [True, False]  # 늦게 온 낮은 seq 는 적용되지 않았다
    detail = client.get(f"/workflow-runs/{run_id}", headers=auth_headers).json()
    assert detail["status"] == "succeeded"
    assert detail["current_node_id"] == "e"
    assert detail["started_at"] is not None
    assert detail["finished_at"] is not None
    assert UUID(detail["workflow_run_id"]) == UUID(run_id)
