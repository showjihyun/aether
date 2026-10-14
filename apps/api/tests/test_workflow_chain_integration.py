"""spec 0005 2.9 개정 2, 2.10, R-6 (P4-2a A): **사슬 하나로** api → 요청 스트림 → 실행기 →
상태 스트림 → 투영 → `GET`.

이 파일이 있는 이유는 **계약이 두 번 구현되기 때문**입니다. `aether:workflow_runs:status` 의
필드를 worker 쪽(`RedisWorkflowStatusNotifier`)과 api 쪽(`WorkflowRunStatusConsumer`)이 서로를
import 하지 않고 각자 만듭니다(AR-7). 그래서 한쪽이 `workflow_run_id` 를 `run_id` 로 쓰거나
시각 형식을 달리 써도 **양쪽 테스트는 전부 통과합니다** — api 쪽 통합 테스트는 스트림 메시지를
손으로 쓰고, worker 쪽은 자기 notifier 의 dict 를 봅니다. 두 구현이 실제로 맞물리는지는 이
사슬만이 판정합니다.

`test_build_production_handler_wires_workflow.py` 는 요청 스트림의 worker 쪽 절반(손으로 쓴
메시지 → `serve()`)을 봅니다. 여기서는 그 메시지를 **api 가** 쓰고, 끝난 뒤의 상태를 **api 가**
투영하는 것까지 봅니다.
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from typing import Any
from uuid import uuid4

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
from aether_api.application.usecases.apply_workflow_run_status import (
    ApplyWorkflowRunStatusUseCase,
)
from aether_api.application.usecases.issue_api_key import IssueApiKeyUseCase
from aether_api.main import create_app
from aether_api.settings import Settings as ApiSettings
from aether_worker.main import serve
from aether_worker.settings import Settings as WorkerSettings
from fastapi.testclient import TestClient
from redis import Redis

from tests.support.pg import DATA_PASSWORD, DATA_ROLE
from tests.support.waiting import wait_until

pytestmark = pytest.mark.integration

_STATUS = "aether:workflow_runs:status"
_API_GROUP = "aether-api"
_JOIN_TIMEOUT = 5.0


def _node(node_id: str, kind: str) -> dict[str, Any]:
    return {"id": node_id, "kind": kind, "max_iterations": None}


def test_a_run_started_through_the_api_is_executed_and_projected_back(
    control_database_url: str,
    db_host_port: tuple[str, int],
    redis_url: str,
    redis_client: Redis,
    control_connection_factory: Callable[[], psycopg.Connection],
) -> None:
    host, port = db_host_port
    api_settings = ApiSettings(database_url=control_database_url, redis_url=redis_url)
    worker_settings = WorkerSettings(
        database_url=f"postgresql+psycopg://{DATA_ROLE}:{DATA_PASSWORD}@{host}:{port}/aether",
        worker_consumer=f"test-chain-{uuid4()}",
        worker_heartbeat_seconds=1,
    )
    issued = IssueApiKeyUseCase(PostgresApiKeyStore(control_connection_factory))(
        f"test-workflow-chain-{uuid4()}"
    )
    headers = {"Authorization": f"Bearer {issued.raw_key}"}
    client = TestClient(create_app(api_settings))

    # api 쪽 투영 소비자와 worker 를 띄웁니다 — 둘 다 **프로덕션 조립**입니다.
    ensure_group(redis_client, _STATUS, _API_GROUP)
    projection = WorkflowRunStatusConsumer(
        redis_client,
        ApplyWorkflowRunStatusUseCase(
            PostgresWorkflowRunDeclarationStore(control_connection_factory)
        ),
        stream=_STATUS,
        group=_API_GROUP,
    )
    stop = threading.Event()
    ready = threading.Event()
    projection_thread = threading.Thread(target=projection.run_until, args=(stop,), daemon=True)
    worker_thread = threading.Thread(
        target=lambda: serve(
            worker_settings, stop=stop, make_client=lambda: redis_client, on_ready=ready.set
        ),
        daemon=True,
    )
    projection_thread.start()
    worker_thread.start()
    try:
        assert ready.wait(_JOIN_TIMEOUT), "worker 가 준비되지 않았습니다"

        created = client.post(
            "/workflows",
            json={
                "name": f"chain-{uuid4()}",
                "nodes": [_node("s", "START"), _node("e", "END")],
                "edges": [{"source": "s", "target": "e", "label": None}],
            },
            headers=headers,
        )
        assert created.status_code == 201, created.text
        started = client.post(
            f"/workflows/{created.json()['id']}/runs", json={"input": {"q": "hi"}}, headers=headers
        )
        assert started.status_code == 202, started.text
        workflow_run_id = started.json()["workflow_run_id"]

        def _detail() -> dict[str, Any]:
            response = client.get(f"/workflow-runs/{workflow_run_id}", headers=headers)
            assert response.status_code == 200, response.text
            body: dict[str, Any] = response.json()
            return body

        assert wait_until(lambda: _detail()["status"] == "succeeded", timeout=20.0), (
            f"사슬이 끊겼습니다 — 마지막으로 본 투영: {_detail()}"
        )
        final = _detail()
        assert final["current_node_id"] == "e", final
        assert final["started_at"] is not None, final
        assert final["finished_at"] is not None, final
        assert final["failure_reason"] is None, final
        assert final["waiting_run_id"] is None, final
    finally:
        stop.set()
        worker_thread.join(_JOIN_TIMEOUT * 2)
        projection_thread.join(_JOIN_TIMEOUT * 2)
