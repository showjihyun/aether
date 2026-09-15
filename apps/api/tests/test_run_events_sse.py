"""spec 0002 2.7, D-4, R-3, R-8, R-12: `GET /runs/{run_id}/events` — SSE 통합 테스트.

PostgreSQL + Redis(testcontainers). `RedisEventSink`(`packages/runtime`)로 이벤트를
직접 심어 worker 없이 스트림 계약(2.7, 2.18)만 검증하는 시나리오(a·b·c·e)와, 실제
worker 를 스레드로 띄워 "단절 뒤 Run 은 계속됩니다"(R-3)를 증명하는 시나리오(d)로
나뉩니다. `sleep` 은 쓰지 않습니다 — `tests.support.waiting.wait_until` 과
`Event.wait`/`asyncio.Event` 만 씁니다(R-11).
"""

from __future__ import annotations

import json
import threading
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from threading import Event
from typing import Any
from uuid import UUID, uuid4

import httpx
import psycopg
import pytest
import uvicorn
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
from aether_runtime.domain.events import EventType, RunEvent
from aether_runtime.domain.tools import ToolCall, ToolResult
from aether_worker.adapters.outbound.noop_trace_context import NoopTraceContext
from aether_worker.application.ports.inbound.handle_run_requested import HandleRunRequested
from aether_worker.application.usecases.handle_run_requested import HandleRunRequestedUseCase
from aether_worker.main import serve as worker_serve
from aether_worker.settings import Settings as WorkerSettings
from fastapi import FastAPI
from fastapi.testclient import TestClient
from redis import Redis

from tests.support.pg import DATA_PASSWORD, DATA_ROLE
from tests.support.waiting import wait_until

pytestmark = pytest.mark.integration

_WORKER_READY_TIMEOUT = 10.0
_JOIN_TIMEOUT = 10.0
_RUN_TIMEOUT = 30.0
_SSE_READ_TIMEOUT = 10.0


@pytest.fixture
def data_database_url(migrated_database: None, db_host_port: tuple[str, int]) -> str:
    host, port = db_host_port
    return f"postgresql+psycopg://{DATA_ROLE}:{DATA_PASSWORD}@{host}:{port}/aether"


def _issue_key(api_settings: Settings, label: str) -> str:
    store = PostgresApiKeyStore(lambda: psycopg.connect(api_settings.psycopg_dsn))
    issued = IssueApiKeyUseCase(store)(label)
    return issued.raw_key


def _create_agent_and_run(client: TestClient, headers: dict[str, str]) -> UUID:
    agent_response = client.post(
        "/agents",
        json={
            "name": f"sse-agent-{uuid4()}",
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
    return UUID(run_response.json()["run_id"])


def _seed_event(run_id: UUID, seq: int, event_type: EventType, payload: dict[str, Any]) -> RunEvent:
    return RunEvent(run_id=run_id, seq=seq, at=datetime.now(UTC), type=event_type, payload=payload)


@dataclass
class _ParsedSseEvent:
    id: str | None
    event: str | None
    data: str


def _parse_sse_lines(lines: Iterator[str]) -> Iterator[_ParsedSseEvent]:
    """줄 단위 SSE 파서 — `id:`/`event:`/`data:` 를 모아 빈 줄에서 이벤트 하나를 냅니다.

    이 통합 테스트가 심는 `data` 는 한 줄짜리 압축 JSON(`RunEvent.model_dump_json()`,
    P1-6 red 증거로 확인)이라 멀티라인 `data:` 조립까지는 다루지 않습니다 — 그
    계약은 sdk 의 `sse.test.ts`(G4)가 별도로 증명합니다.
    """
    event_id: str | None = None
    event_type: str | None = None
    data_parts: list[str] = []
    for raw_line in lines:
        line = raw_line.rstrip("\r")
        if line == "":
            if data_parts:
                yield _ParsedSseEvent(id=event_id, event=event_type, data="\n".join(data_parts))
            event_id, event_type, data_parts = None, None, []
            continue
        if line.startswith("id:"):
            event_id = line[len("id:") :].strip()
        elif line.startswith("event:"):
            event_type = line[len("event:") :].strip()
        elif line.startswith("data:"):
            data_parts.append(line[len("data:") :].strip())


def test_events_are_streamed_in_seeded_order_and_close_after_run_finished(
    control_database_url: str,
    redis_url: str,
    redis_client: Redis,
) -> None:
    """spec 2.7: `id` == `seq`, `event` == `type`, 순서 == 심은 순서, `run.finished` 뒤 닫힘."""
    api_settings = Settings(database_url=control_database_url, redis_url=redis_url)
    app = create_app(api_settings)

    with TestClient(app) as client:
        headers = {"Authorization": f"Bearer {_issue_key(api_settings, f'sse-{uuid4()}')}"}
        run_id = _create_agent_and_run(client, headers)

        sink = RedisEventSink(redis_client)
        seeded = [
            _seed_event(run_id, 1, "run.status", {"status": "queued"}),
            _seed_event(run_id, 2, "run.status", {"status": "running"}),
            _seed_event(run_id, 3, "task.started", {"task_id": "t1", "step": 1}),
            _seed_event(run_id, 4, "task.finished", {"task_id": "t1"}),
            _seed_event(run_id, 5, "run.finished", {"status": "succeeded"}),
        ]
        for event in seeded:
            sink.publish(event)

        with client.stream("GET", f"/runs/{run_id}/events", headers=headers) as response:
            assert response.status_code == 200
            assert response.headers["content-type"].startswith("text/event-stream")
            parsed = list(_parse_sse_lines(response.iter_lines()))

    assert [p.id for p in parsed] == ["1", "2", "3", "4", "5"]
    assert [p.event for p in parsed] == [
        "run.status",
        "run.status",
        "task.started",
        "task.finished",
        "run.finished",
    ]


def test_last_event_id_resumes_after_the_given_seq(
    control_database_url: str,
    redis_url: str,
    redis_client: Redis,
) -> None:
    """spec 2.7: `Last-Event-ID: 3` → 스트림 ID `3-0` 다음, 즉 `seq 4` 부터."""
    api_settings = Settings(database_url=control_database_url, redis_url=redis_url)
    app = create_app(api_settings)

    with TestClient(app) as client:
        headers = {"Authorization": f"Bearer {_issue_key(api_settings, f'sse-{uuid4()}')}"}
        run_id = _create_agent_and_run(client, headers)

        sink = RedisEventSink(redis_client)
        for event in [
            _seed_event(run_id, 1, "run.status", {"status": "queued"}),
            _seed_event(run_id, 2, "run.status", {"status": "running"}),
            _seed_event(run_id, 3, "task.started", {"task_id": "t1", "step": 1}),
            _seed_event(run_id, 4, "task.finished", {"task_id": "t1"}),
            _seed_event(run_id, 5, "run.finished", {"status": "succeeded"}),
        ]:
            sink.publish(event)

        headers_with_last_event_id = {**headers, "Last-Event-ID": "3"}
        with client.stream(
            "GET", f"/runs/{run_id}/events", headers=headers_with_last_event_id
        ) as response:
            assert response.status_code == 200
            parsed = list(_parse_sse_lines(response.iter_lines()))

    assert [p.id for p in parsed] == ["4", "5"]


def test_missing_stream_with_terminal_run_yields_synthetic_run_finished_and_closes(
    control_database_url: str,
    redis_url: str,
    admin_connection_factory: Callable[[], psycopg.Connection],
) -> None:
    """spec 2.7 "스트림이 없을 때": 종결이면 합성 `run.finished` 하나 뒤 닫힘."""
    api_settings = Settings(database_url=control_database_url, redis_url=redis_url)
    app = create_app(api_settings)

    with TestClient(app) as client:
        headers = {"Authorization": f"Bearer {_issue_key(api_settings, f'sse-{uuid4()}')}"}
        run_id = _create_agent_and_run(client, headers)

        with admin_connection_factory() as admin_conn, admin_conn.cursor() as cur:
            cur.execute(
                "UPDATE control.runs SET status = 'succeeded' WHERE id = %s", (str(run_id),)
            )
            admin_conn.commit()

        with client.stream("GET", f"/runs/{run_id}/events", headers=headers) as response:
            assert response.status_code == 200
            parsed = list(_parse_sse_lines(response.iter_lines()))

    assert len(parsed) == 1
    assert parsed[0].event == "run.finished"
    assert parsed[0].id == "1"
    body = json.loads(parsed[0].data)
    assert body["run_id"] == str(run_id)
    assert body["type"] == "run.finished"
    assert body["payload"] == {"status": "succeeded"}


def test_events_for_missing_run_returns_404(
    control_database_url: str,
    redis_url: str,
) -> None:
    api_settings = Settings(database_url=control_database_url, redis_url=redis_url)
    app = create_app(api_settings)

    with TestClient(app) as client:
        headers = {"Authorization": f"Bearer {_issue_key(api_settings, f'sse-{uuid4()}')}"}

        response = client.get(f"/runs/{uuid4()}/events", headers=headers)

    assert response.status_code == 404
    assert response.json()["detail"] == "run_not_found"


# --- (d) 단절 뒤 Run 은 계속됩니다(R-3) — 실제 worker, gated tool -------------------


@dataclass
class _GatedClockTool:
    name: str = "clock"
    description: str = "gated clock for the sse disconnect test"
    input_schema: dict[str, Any] = field(default_factory=dict)
    reached: Event = field(default_factory=Event)
    gate: Event = field(default_factory=Event)

    def run(self, arguments: dict[str, Any]) -> ToolResult:
        del arguments
        self.reached.set()
        self.gate.wait()
        return ToolResult(content="12:00:00")


class _SingleToolRegistry:
    def __init__(self, tool: _GatedClockTool) -> None:
        self._tool = tool

    def get(self, name: str) -> _GatedClockTool:
        if name != self._tool.name:
            raise KeyError(name)
        return self._tool

    def names(self) -> frozenset[str]:
        return frozenset({self._tool.name})


def _build_gated_handler(
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
        owner="sse-disconnect-worker",
    )
    return HandleRunRequestedUseCase(execute_run, NoopTraceContext())


@contextmanager
def _running_server(app: FastAPI) -> Iterator[str]:
    """`app` 을 실제 `uvicorn` 서버(임시 포트)로 띄우고 base URL 을 냅니다.

    `TestClient`(httpx `ASGITransport`)는 ASGI 앱을 **완결될 때까지 돌려 응답
    바디를 통째로 모은 뒤** `Response` 를 돌려줍니다 — 서버가 도구 호출 중간에
    멈춰 있는 동안(이 시나리오처럼) 클라이언트가 이미 나간 바이트를 실시간으로
    받지 못하고, 서버가 끝나야만(여기서는 영영 끝나지 않음) 받습니다(직접 재현해
    확인함 — `asyncio.sleep` 으로 멈추는 최소 예제도 같은 방식으로 무한 대기).
    그래서 이 테스트만 실제 TCP 소켓으로 스트리밍하는 진짜 서버를 씁니다 — 클라이언트
    단절 감지(Starlette 의 `listen_for_disconnect`)도 실제 연결이 있어야 의미가
    있습니다.
    """
    config = uvicorn.Config(app, host="127.0.0.1", port=0, log_level="warning")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    try:
        assert wait_until(lambda: server.started, timeout=_WORKER_READY_TIMEOUT), (
            "uvicorn 서버가 시작되지 않았습니다"
        )
        port = server.servers[0].sockets[0].getsockname()[1]
        yield f"http://127.0.0.1:{port}"
    finally:
        server.should_exit = True
        thread.join(_JOIN_TIMEOUT)


def test_run_keeps_going_after_the_sse_client_disconnects(
    control_database_url: str,
    data_connection_factory: Callable[[], psycopg.Connection],
    redis_url: str,
    redis_client: Redis,
) -> None:
    """spec 2.7 "종료", R-3: SSE 소비자를 도구 호출 도중에 닫아도 Run 은 계속되어
    `succeeded` 에 이릅니다 — worker 는 api 의 SSE 독자를 모릅니다(AR-7)."""
    api_settings = Settings(database_url=control_database_url, redis_url=redis_url)
    app = create_app(api_settings)

    gated_tool = _GatedClockTool()
    handler = _build_gated_handler(data_connection_factory, redis_client, gated_tool)

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

        with (
            _running_server(app) as base_url,
            httpx.Client(base_url=base_url, timeout=30.0) as client,
        ):
            headers = {"Authorization": f"Bearer {_issue_key(api_settings, f'sse-disc-{uuid4()}')}"}
            agent_response = client.post(
                "/agents",
                json={
                    "name": f"sse-disc-agent-{uuid4()}",
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

            saw_tool_called = False
            with client.stream("GET", f"/runs/{run_id}/events", headers=headers) as response:
                assert response.status_code == 200
                for parsed in _parse_sse_lines(response.iter_lines()):
                    if parsed.event == "tool.called":
                        saw_tool_called = True
                        break
            assert saw_tool_called, "tool.called 이벤트를 SSE 로 받지 못했습니다"

            gated_tool.gate.set()

            def _is_succeeded() -> bool:
                get_response = client.get(f"/runs/{run_id}", headers=headers)
                if get_response.status_code != 200:
                    return False
                return bool(get_response.json()["status"] == "succeeded")

            assert wait_until(_is_succeeded, timeout=_RUN_TIMEOUT), (
                f"단절 뒤 {_RUN_TIMEOUT}초 안에 succeeded 에 이르지 못했습니다"
            )
    finally:
        gated_tool.gate.set()
        worker_stop.set()
        worker_thread.join(_JOIN_TIMEOUT)
