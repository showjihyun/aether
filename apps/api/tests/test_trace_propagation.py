"""spec 0002 2.9, 2.18, R-5 (P1-8): api·worker·collector 를 잇는 trace 전파의 e2e.

api(lifespan, `request_tracing=OtelRequestTracing(provider)`) + worker
`serve(handler=...)` 스레드(실제 PostgreSQL/Redis 어댑터 + `OtelTracer(provider)` +
`HandleRunRequestedUseCase(execute, OtelTraceContext())`, P1-5b e2e 패턴) — 한
`TracerProvider` + `InMemorySpanExporter` 를 api 와 worker 가 공유합니다(전역
`trace.set_tracer_provider` 는 부르지 않습니다 — 어댑터에 직접 주입).

키 발급 → agent(도구 `clock`) → run → `wait_until(GET status == "succeeded")` 뒤:

1. `aether:runs:requested` 스트림 메시지의 `traceparent` 가 W3C 형식이고 비어 있지
   않습니다(2.18).
2. exporter 의 `run.request` span(api)과 `run` span(worker)이 같은 trace id 이고,
   `run` 의 parent span id 가 `run.request` 의 span id 와 같습니다(2.9 전파).
3. `GET /runs/{id}` 의 `trace_id` 가 그 trace id 와 같습니다(R-5).
4. `task`·`model.complete` span 이 `run` 아래에 있습니다(2.9 span 트리).
"""

from __future__ import annotations

import re
import threading
from collections.abc import Callable
from threading import Event
from uuid import uuid4

import psycopg
import pytest
from aether_api.adapters.outbound.db.api_keys import PostgresApiKeyStore
from aether_api.adapters.outbound.otel_request_tracing import OtelRequestTracing
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
from aether_runtime.adapters.outbound.telemetry.otel_tracer import OtelTracer
from aether_runtime.adapters.outbound.tools.registry import InMemoryToolRegistry
from aether_runtime.application.ports.outbound.model_gateway import ModelResponse
from aether_runtime.application.usecases.execute_run import ExecuteRunUseCase
from aether_runtime.domain.tools import ToolCall
from aether_worker.adapters.outbound.otel_trace_context import OtelTraceContext
from aether_worker.application.usecases.handle_run_requested import HandleRunRequestedUseCase
from aether_worker.main import serve as worker_serve
from aether_worker.settings import Settings as WorkerSettings
from fastapi.testclient import TestClient
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from redis import Redis

from tests.support.waiting import wait_until

pytestmark = pytest.mark.integration

_WORKER_READY_TIMEOUT = 10.0
_JOIN_TIMEOUT = 10.0
_RUN_TIMEOUT = 30.0
_TRACEPARENT_RE = re.compile(r"00-[0-9a-f]{32}-[0-9a-f]{16}-[0-9a-f]{2}")


def _xrange_all(client: Redis, stream: str) -> list[tuple[str, dict[str, str]]]:
    """`xrange` 의 반환 타입은(redis-py 스텁 상) `bytes | str` 및 `None` 을 허용합니다
    — `decode_responses=True` 로 접속했으므로 런타임에는 항상 `str` 이지만, 정적
    타입은 그것을 모릅니다(`apps/api/tests/test_run_notifier.py` 와 같은 헬퍼)."""
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


def _issue_key(api_settings: Settings, label: str) -> str:
    store = PostgresApiKeyStore(lambda: psycopg.connect(api_settings.psycopg_dsn))
    issued = IssueApiKeyUseCase(store)(label)
    return issued.raw_key


def test_trace_id_propagates_from_api_request_span_through_worker_run_span(
    control_database_url: str,
    data_connection_factory: Callable[[], psycopg.Connection],
    redis_url: str,
    redis_client: Redis,
) -> None:
    provider = TracerProvider()
    exporter = InMemorySpanExporter()
    provider.add_span_processor(SimpleSpanProcessor(exporter))

    api_settings = Settings(database_url=control_database_url, redis_url=redis_url)
    app = create_app(api_settings, request_tracing=OtelRequestTracing(provider))

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
        InMemoryToolRegistry(SystemClock()),
        RedisEventSink(redis_client),
        RedisStatusNotifier(redis_client),
        OtelTracer(provider),
        SystemClock(),
        owner="trace-e2e-worker",
    )
    handler = HandleRunRequestedUseCase(execute_run, OtelTraceContext())

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
                "Authorization": f"Bearer {_issue_key(api_settings, f'trace-e2e-{uuid4()}')}"
            }

            agent_response = client.post(
                "/agents",
                json={
                    "name": f"trace-e2e-agent-{uuid4()}",
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

            def _is_succeeded() -> bool:
                response = client.get(f"/runs/{run_id}", headers=headers)
                if response.status_code != 200:
                    return False
                return bool(response.json()["status"] == "succeeded")

            assert wait_until(_is_succeeded, timeout=_RUN_TIMEOUT), (
                f"{_RUN_TIMEOUT}초 안에 succeeded 에 이르지 못했습니다"
            )

            run_view = client.get(f"/runs/{run_id}", headers=headers).json()
    finally:
        worker_stop.set()
        worker_thread.join(_JOIN_TIMEOUT)

    # 1. requested 스트림 메시지의 traceparent 가 W3C 형식이고 비어 있지 않음(2.18).
    requested_entries = _xrange_all(redis_client, "aether:runs:requested")
    matching = [
        fields for _message_id, fields in requested_entries if fields.get("run_id") == run_id
    ]
    assert len(matching) == 1, matching
    wire_traceparent = matching[0]["traceparent"]
    assert wire_traceparent
    assert _TRACEPARENT_RE.fullmatch(wire_traceparent), wire_traceparent

    # 2. run.request(api) 와 run(worker) span 이 같은 trace, run 의 parent 가 run.request.
    spans_by_name = {span.name: span for span in exporter.get_finished_spans()}
    assert "run.request" in spans_by_name
    assert "run" in spans_by_name
    request_span = spans_by_name["run.request"]
    run_span = spans_by_name["run"]
    assert run_span.context.trace_id == request_span.context.trace_id
    assert run_span.parent is not None
    assert run_span.parent.span_id == request_span.context.span_id

    trace_id_hex = format(run_span.context.trace_id, "032x")
    assert trace_id_hex in wire_traceparent

    # 3. GET /runs/{id} 의 trace_id 가 그 trace id 와 같음(R-5).
    assert run_view["trace_id"] == trace_id_hex

    # 4. task·model.complete span 이 run 아래.
    assert "task" in spans_by_name
    assert "model.complete" in spans_by_name
    assert spans_by_name["task"].parent is not None
    assert spans_by_name["task"].parent.span_id == run_span.context.span_id
    assert spans_by_name["model.complete"].parent is not None
    assert spans_by_name["model.complete"].parent.span_id == spans_by_name["task"].context.span_id
