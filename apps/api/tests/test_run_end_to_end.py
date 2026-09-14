"""spec 0002 R-2 (P1-5b): api + worker 를 같은 프로세스의 스레드로 띄운 e2e.

(a) api 앱(lifespan 포함, `with TestClient(app) as client:`) + worker `serve()`
스레드(프로덕션 조립, fake 모델 echo) → 키 발급 → agent → run →
`wait_until(GET status == "succeeded", 30초)`.

(b) 취소: worker 를 `handler=` 주입으로 띄웁니다 — `ExecuteRunUseCase` 를 실제
PostgreSQL/Redis 어댑터 + `FakeModelGateway(scenario=[tool_call(clock) 1회, 최종
텍스트])` + **`Event` 로 막히는 gated `Tool`**(첫 도구 호출에서 대기)로 조립합니다.
run 을 시작해 도구가 막힌 동안 `POST cancel` 하고 `Event` 를 풀면, 다음 반복
시작에서 취소가 관측되어(`ExecuteRunUseCase._execute` 의 `while True` 최상단이
매 반복마다 `cancel_requested_at` 을 다시 읽습니다) `cancelled` 로 끝납니다(D-11).

`sleep` 은 쓰지 않습니다 — `tests.support.waiting.wait_until` 과 `Event.wait` 만.
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from dataclasses import dataclass, field
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
from aether_runtime.adapters.outbound.system_clock import SystemClock
from aether_runtime.adapters.outbound.telemetry.noop_tracer import NoopTracer
from aether_runtime.application.ports.outbound.model_gateway import ModelResponse
from aether_runtime.application.usecases.execute_run import ExecuteRunUseCase
from aether_runtime.domain.tools import ToolCall, ToolResult
from aether_worker.adapters.outbound.noop_trace_context import NoopTraceContext
from aether_worker.application.ports.inbound.handle_run_requested import HandleRunRequested
from aether_worker.application.usecases.handle_run_requested import HandleRunRequestedUseCase
from aether_worker.main import serve as worker_serve
from aether_worker.settings import Settings as WorkerSettings
from fastapi.testclient import TestClient
from redis import Redis

from tests.support.pg import DATA_PASSWORD, DATA_ROLE
from tests.support.waiting import wait_until

pytestmark = pytest.mark.integration

_WORKER_READY_TIMEOUT = 10.0
_JOIN_TIMEOUT = 10.0
_RUN_TIMEOUT = 30.0


@pytest.fixture
def data_database_url(migrated_database: None, db_host_port: tuple[str, int]) -> str:
    """worker 의 `Settings.database_url` — `aether_data` 역할(spec 0002 2.15).

    `admin_database_url`/`control_database_url` 과 같은 관리자 db 이름("aether")을
    씁니다(`tests/support/pg.py` 의 컨테이너는 이 db 하나뿐입니다)."""
    host, port = db_host_port
    return f"postgresql+psycopg://{DATA_ROLE}:{DATA_PASSWORD}@{host}:{port}/aether"


def _issue_key(api_settings: Settings, label: str) -> str:
    store = PostgresApiKeyStore(lambda: psycopg.connect(api_settings.psycopg_dsn))
    issued = IssueApiKeyUseCase(store)(label)
    return issued.raw_key


def test_run_reaches_succeeded_via_worker_loop(
    control_database_url: str,
    data_database_url: str,
    redis_url: str,
) -> None:
    """spec 0002 R-2: api(lifespan) + worker `serve()` 스레드, fake 모델(echo) →
    `GET /runs/{id}` 가 `succeeded` 에 이릅니다."""
    api_settings = Settings(database_url=control_database_url, redis_url=redis_url)
    app = create_app(api_settings)

    worker_settings = WorkerSettings(
        redis_url=redis_url, database_url=data_database_url, model_adapter="fake"
    )
    worker_stop = Event()
    worker_ready = Event()
    worker_thread = threading.Thread(
        target=worker_serve,
        args=(worker_settings,),
        kwargs={"stop": worker_stop, "on_ready": worker_ready.set},
        daemon=True,
    )
    worker_thread.start()

    try:
        assert worker_ready.wait(timeout=_WORKER_READY_TIMEOUT), "worker 가 준비되지 않았습니다"

        with TestClient(app) as client:
            headers = {"Authorization": f"Bearer {_issue_key(api_settings, f'e2e-{uuid4()}')}"}

            agent_response = client.post(
                "/agents",
                json={
                    "name": f"e2e-agent-{uuid4()}",
                    "definition": {"schema_version": 1, "system_prompt": "You are a helper."},
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

            def _is_succeeded() -> bool:
                response = client.get(f"/runs/{run_id}", headers=headers)
                if response.status_code != 200:
                    return False
                return bool(response.json()["status"] == "succeeded")

            assert wait_until(_is_succeeded, timeout=_RUN_TIMEOUT), (
                f"{_RUN_TIMEOUT}초 안에 succeeded 에 이르지 못했습니다"
            )
    finally:
        worker_stop.set()
        worker_thread.join(_JOIN_TIMEOUT)


@dataclass
class _GatedClockTool:
    """`clock` 이름의 도구지만 `run()` 이 `gate` 가 열릴 때까지 멈춥니다 — 취소
    시나리오가 도구 호출 도중(다음 반복 전)에 `cancel_requested_at` 을 심을 수
    있는 창을 만듭니다."""

    name: str = "clock"
    description: str = "gated clock for the cancel e2e test"
    input_schema: dict[str, Any] = field(default_factory=dict)
    reached: Event = field(default_factory=Event)
    gate: Event = field(default_factory=Event)

    def run(self, arguments: dict[str, Any]) -> ToolResult:
        del arguments
        self.reached.set()
        self.gate.wait()
        return ToolResult(content="12:00:00")


class _SingleToolRegistry:
    """`ToolRegistry` 포트의 최소 구현 — `_GatedClockTool` 하나만 압니다."""

    def __init__(self, tool: _GatedClockTool) -> None:
        self._tool = tool

    def get(self, name: str) -> _GatedClockTool:
        if name != self._tool.name:
            raise KeyError(name)
        return self._tool

    def names(self) -> frozenset[str]:
        return frozenset({self._tool.name})


def _build_cancel_test_handler(
    data_connection_factory: Callable[[], psycopg.Connection],
    redis_client: Redis,
    gated_tool: _GatedClockTool,
) -> HandleRunRequested:
    execute_run = ExecuteRunUseCase(
        PostgresRunStateStore(data_connection_factory),
        PostgresRunDeclarationReader(data_connection_factory),
        FakeModelGateway(
            scenario=[
                ModelResponse(
                    tool_calls=[ToolCall(id="call_1", name="clock", arguments={})],
                    finish_reason="tool_calls",
                ),
                ModelResponse(text="final answer.", finish_reason="stop"),
            ]
        ),
        _SingleToolRegistry(gated_tool),
        RedisEventSink(redis_client),
        RedisStatusNotifier(redis_client),
        NoopTracer(),
        SystemClock(),
        owner="e2e-cancel-worker",
    )
    return HandleRunRequestedUseCase(execute_run, NoopTraceContext())


def test_cancel_stops_the_run_at_the_next_iteration(
    control_database_url: str,
    data_connection_factory: Callable[[], psycopg.Connection],
    redis_url: str,
    redis_client: Redis,
) -> None:
    """spec 0002 R-2, D-11: 도구 호출이 막힌 동안 `cancel` 하면, 다음 반복 시작에서
    관측되어 `cancelled` 로 끝납니다(협력적 취소, C-3)."""
    api_settings = Settings(database_url=control_database_url, redis_url=redis_url)
    app = create_app(api_settings)

    gated_tool = _GatedClockTool()
    handler = _build_cancel_test_handler(data_connection_factory, redis_client, gated_tool)

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
                "Authorization": f"Bearer {_issue_key(api_settings, f'e2e-cancel-{uuid4()}')}"
            }

            agent_response = client.post(
                "/agents",
                json={
                    "name": f"e2e-cancel-agent-{uuid4()}",
                    "definition": {
                        "schema_version": 1,
                        "system_prompt": "You are a helper.",
                        "tools": ["clock"],
                    },
                },
                headers=headers,
            )
            assert agent_response.status_code == 201, agent_response.text
            agent_id = agent_response.json()["id"]

            run_response = client.post(
                f"/agents/{agent_id}/run", json={"input": "what time is it"}, headers=headers
            )
            assert run_response.status_code == 202, run_response.text
            run_id = run_response.json()["run_id"]

            assert gated_tool.reached.wait(timeout=_WORKER_READY_TIMEOUT), (
                "도구 호출이 시작되지 않았습니다"
            )

            cancel_response = client.post(f"/runs/{run_id}/cancel", headers=headers)
            assert cancel_response.status_code == 202, cancel_response.text

            gated_tool.gate.set()

            def _is_cancelled() -> bool:
                response = client.get(f"/runs/{run_id}", headers=headers)
                if response.status_code != 200:
                    return False
                return bool(response.json()["status"] == "cancelled")

            assert wait_until(_is_cancelled, timeout=_RUN_TIMEOUT), (
                f"{_RUN_TIMEOUT}초 안에 cancelled 에 이르지 못했습니다"
            )
    finally:
        gated_tool.gate.set()  # 아직 막혀 있다면 스레드가 종료될 수 있도록 풀어줍니다.
        worker_stop.set()
        worker_thread.join(_JOIN_TIMEOUT)
