"""spec 0002 2.8, R-2, R-4, C-13 (P1-7): 재시도 소진 → `failed(model_error)` 투영이
`GET /runs/{id}` 에 실제로 도달합니다.

api lifespan + worker `serve(handler=...)` 스레드(P1-5b e2e 패턴, `test_run_end_to_
end.py` 의 `_build_cancel_test_handler` 와 같은 조립 방식) — 핸들러는 이 테스트에서
실제 PostgreSQL/Redis 어댑터 + `FakeModelGateway(scenario=[ModelError("http",
status=500)] * 3)` + `model_retries=2` 정의로 조립합니다. `SystemClock` 대신 즉시
반환하는 테스트 전용 `Clock`(`sleep` 은 기록만)을 써서 재시도 백오프를 실제로
기다리지 않습니다.

이 unit(P1-7)이 execute_run.py 에 재시도 정책을 이미 더했으므로, 이 통합 테스트는
작성 시점부터 green 입니다 — "정책이 없으면 첫 500 에서 이미 failed 로 끝나
`len(gateway.calls) == 3` 단언에서 실패한다" 는 시나리오는 P1-4 시절의 동작을
가리키며, `test_policy.py`(G2)의 red→green 사이클이 이미 그 부분을 별도로 증명했다는
사실을 구현 보고에 남깁니다. 이 파일은 그 정책이 worker+api+PostgreSQL+Redis 조립
전체를 통해 실제로 투영되는지를 검증합니다.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from threading import Event
from typing import Any
from uuid import uuid4

import psycopg
import pytest
from aether_api.adapters.outbound.db.api_keys import PostgresApiKeyStore
from aether_api.application.usecases.issue_api_key import IssueApiKeyUseCase
from aether_api.main import create_app
from aether_api.settings import Settings
from aether_runtime.adapters.outbound.db.run_declaration_reader import (
    PostgresRunDeclarationReader,
)
from aether_runtime.adapters.outbound.db.run_state_store import PostgresRunStateStore
from aether_runtime.adapters.outbound.model_gateway.fake import FakeModelGateway
from aether_runtime.adapters.outbound.redis.event_sink import RedisEventSink
from aether_runtime.adapters.outbound.redis.status_notifier import RedisStatusNotifier
from aether_runtime.adapters.outbound.telemetry.noop_tracer import NoopTracer
from aether_runtime.adapters.outbound.tools.registry import InMemoryToolRegistry
from aether_runtime.application.ports.outbound.model_gateway import ModelError
from aether_runtime.application.usecases.execute_run import ExecuteRunUseCase
from aether_worker.adapters.outbound.noop_trace_context import NoopTraceContext
from aether_worker.application.ports.inbound.handle_run_requested import HandleRunRequested
from aether_worker.application.usecases.handle_run_requested import HandleRunRequestedUseCase
from aether_worker.main import serve as worker_serve
from aether_worker.settings import Settings as WorkerSettings
from fastapi.testclient import TestClient
from redis import Redis

from tests.support.waiting import wait_until

pytestmark = pytest.mark.integration

_WORKER_READY_TIMEOUT = 10.0
_JOIN_TIMEOUT = 10.0
_RUN_TIMEOUT = 30.0


@dataclass
class _ImmediateClock:
    """`Clock` 포트를 만족하되 `sleep` 은 즉시 반환하고 인자만 기록합니다(spec 0002
    R-11) -- `SystemClock` 대신 써서 재시도 백오프를 실제로 기다리지 않습니다."""

    sleeps: list[float] = field(default_factory=list)

    def now(self) -> datetime:
        return datetime.now(UTC)

    def monotonic(self) -> float:
        return time.monotonic()

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)


def _issue_key(api_settings: Settings, label: str) -> str:
    store = PostgresApiKeyStore(lambda: psycopg.connect(api_settings.psycopg_dsn))
    issued = IssueApiKeyUseCase(store)(label)
    return issued.raw_key


def _build_retry_exhausted_handler(
    data_connection_factory: Callable[[], psycopg.Connection],
    redis_client: Redis,
    gateway: FakeModelGateway,
    clock: _ImmediateClock,
) -> HandleRunRequested:
    execute_run = ExecuteRunUseCase(
        PostgresRunStateStore(data_connection_factory),
        PostgresRunDeclarationReader(data_connection_factory),
        gateway,
        InMemoryToolRegistry(clock),
        RedisEventSink(redis_client),
        RedisStatusNotifier(redis_client),
        NoopTracer(),
        clock,
        owner="e2e-retry-worker",
    )
    return HandleRunRequestedUseCase(execute_run, NoopTraceContext())


def test_model_error_retries_exhaust_and_project_as_failed(
    control_database_url: str,
    data_connection_factory: Callable[[], psycopg.Connection],
    redis_url: str,
    redis_client: Redis,
) -> None:
    """spec 0002 2.8, R-2, R-4: `model_retries=2` 에서 5xx 가 시도 전부(3회) 나면
    `GET /runs/{id}` 의 `status == "failed"`, `failure_reason == "model_error"`,
    `finished_at` 존재 -- 재시도 예산이 실제로 소진되었음을 `gateway.calls` 로도
    확인합니다."""
    api_settings = Settings(database_url=control_database_url, redis_url=redis_url)
    app = create_app(api_settings)

    gateway = FakeModelGateway(scenario=[ModelError(kind="http", status=500)] * 3)
    clock = _ImmediateClock()
    handler = _build_retry_exhausted_handler(data_connection_factory, redis_client, gateway, clock)

    worker_settings = WorkerSettings(redis_url=redis_url)
    worker_stop = Event()
    worker_ready = Event()
    worker_thread = threading.Thread(
        target=worker_serve,
        args=(worker_settings,),
        kwargs={"stop": worker_stop, "on_ready": worker_ready.set, "handler": handler},
        daemon=True,
    )
    worker_thread.start()

    try:
        assert worker_ready.wait(timeout=_WORKER_READY_TIMEOUT), "worker 가 준비되지 않았습니다"

        with TestClient(app) as client:
            headers = {
                "Authorization": f"Bearer {_issue_key(api_settings, f'e2e-retry-{uuid4()}')}"
            }

            agent_response = client.post(
                "/agents",
                json={
                    "name": f"e2e-retry-agent-{uuid4()}",
                    "definition": {
                        "schema_version": 1,
                        "system_prompt": "You are a helper.",
                        "policy": {"model_retries": 2},
                    },
                },
                headers=headers,
            )
            assert agent_response.status_code == 201, agent_response.text
            agent_id = agent_response.json()["id"]

            run_response = client.post(
                f"/agents/{agent_id}/run", json={"input": "hello there"}, headers=headers
            )
            assert run_response.status_code == 202, run_response.text
            run_id = run_response.json()["run_id"]

            def _get_run() -> dict[str, Any]:
                response = client.get(f"/runs/{run_id}", headers=headers)
                assert response.status_code == 200, response.text
                return dict(response.json())

            def _is_failed() -> bool:
                return bool(_get_run()["status"] == "failed")

            assert wait_until(_is_failed, timeout=_RUN_TIMEOUT), (
                f"{_RUN_TIMEOUT}초 안에 failed 에 이르지 못했습니다"
            )

            final = _get_run()
            assert final["failure_reason"] == "model_error"
            assert final["finished_at"] is not None
            assert len(gateway.calls) == 3, (
                "재시도가 모델 예산(model_retries + 1) 만큼 소진되어야 합니다"
            )
    finally:
        worker_stop.set()
        worker_thread.join(_JOIN_TIMEOUT)
