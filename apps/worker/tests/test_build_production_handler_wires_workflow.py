"""spec 0005 2.1, 2.9 개정 2 (P4-2a A, B2): worker 의 **프로덕션 조립**이 Workflow 소비자를 실제로
띄우는지.

`test_workflow_executor_integration.py` 는 손으로 반복한 조립이 올바른지 증명합니다. 여기서는
"worker 의 실제 조립(`_build_production_workflow_handler`, `serve()`)이 그것을 꽂는가" 만 봅니다.
꽂지 않으면(handler 가 없거나, 스레드가 안 뜨거나, 어댑터가 빠지면) 요청이 영원히 처리되지
않고 조용히 `queued` 로 남습니다 - 이 파일이 그 침묵을 실패로 바꿉니다.
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from uuid import UUID, uuid4

import psycopg
import pytest
from aether_worker.adapters.outbound.db.parked_workflow_finder import (
    PostgresParkedWorkflowFinder,
)
from aether_worker.adapters.outbound.redis.workflow_requeuer import RedisWorkflowRequeuer
from aether_worker.application.ports.inbound.handle_ingestion_requested import (
    HandleIngestionOutcome,
    IngestionRequestedMessage,
)
from aether_worker.application.ports.inbound.handle_run_requested import (
    HandleOutcome,
    RequestedMessage,
)
from aether_worker.application.usecases.resume_parked_workflows import (
    ResumeParkedWorkflowsUseCase,
)
from aether_worker.main import (
    _build_production_resume,
    _build_production_workflow_handler,
    serve,
)
from aether_worker.settings import Settings
from aether_workflow.adapters.outbound.db.agent_run_reader import PostgresAgentRunReader
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
from aether_workflow.application.usecases.advance_workflow_run import AdvanceWorkflowRunUseCase
from aether_workflow.domain.node import Edge, Node, NodeKind
from redis import Redis

from tests.support.pg import DATA_PASSWORD, DATA_ROLE
from tests.support.waiting import wait_until
from tests.support.workflow_db import declare_workflow_run

pytestmark = pytest.mark.integration

_STOP_JOIN_TIMEOUT = 5.0


def _data_url(db_host_port: tuple[str, int]) -> str:
    host, port = db_host_port
    return f"postgresql+psycopg://{DATA_ROLE}:{DATA_PASSWORD}@{host}:{port}/aether"


def test_production_workflow_handler_wires_every_port(
    migrated_database: None, db_host_port: tuple[str, int], redis_client: Redis
) -> None:
    settings = Settings(database_url=_data_url(db_host_port))

    handler = _build_production_workflow_handler(settings, redis_client)

    advance = handler._advance  # type: ignore[attr-defined]
    assert isinstance(advance, AdvanceWorkflowRunUseCase)
    assert isinstance(advance._store, PostgresWorkflowRunStateStore)
    assert isinstance(advance._reader, PostgresWorkflowRunDeclarationReader)
    assert isinstance(advance._sink, RedisWorkflowEventSink)
    assert isinstance(advance._notifier, RedisWorkflowStatusNotifier)
    assert isinstance(advance._agent_runs, PostgresAgentRunReader)
    assert isinstance(advance._launcher, RedisAgentRunLauncher)
    assert advance._owner == settings.worker_consumer
    assert advance._lease_ttl_seconds == settings.worker_lease_seconds


def test_production_resume_wires_the_finder_and_the_requeuer(
    migrated_database: None, db_host_port: tuple[str, int], redis_client: Redis
) -> None:
    """빠른 경로와 스위퍼가 쓰는 재개 유스케이스의 조립: `aether_data` 로 읽는 찾기와, 요청 스트림에
    싣는 재큐."""
    settings = Settings(database_url=_data_url(db_host_port))

    resume = _build_production_resume(settings, redis_client)

    assert isinstance(resume, ResumeParkedWorkflowsUseCase)
    assert isinstance(resume._finder, PostgresParkedWorkflowFinder)
    assert isinstance(resume._requeuer, RedisWorkflowRequeuer)


class _CountingResume:
    """`serve()` 가 빠른 경로 소비자와 스위퍼 스레드를 **둘 다** 실제로 띄우는지 세는 주입물."""

    def __init__(self) -> None:
        self.finished: list[UUID] = []
        self.sweeps = 0

    def on_agent_run_finished(self, agent_run_id: UUID) -> int:
        self.finished.append(agent_run_id)
        return 0

    def sweep(self) -> int:
        self.sweeps += 1
        return 0


def test_serve_starts_both_the_wake_consumer_and_the_sweeper(
    migrated_database: None, db_host_port: tuple[str, int], redis_client: Redis
) -> None:
    """깨우는 경로 둘이 조립에서 빠지면 파킹된 Workflow 가 영원히 깨지 않는다 - 그리고 아무도
    모른다.
    종결 통지 하나를 스트림에 넣으면 빠른 경로 스레드가 받고, 스위퍼 스레드는 시작하자마자
    훑는다."""
    settings = Settings(
        database_url=_data_url(db_host_port),
        worker_consumer=f"test-consumer-{uuid4()}",
        worker_heartbeat_seconds=1,
        workflow_sweep_interval_seconds=0.05,
    )
    resume = _CountingResume()
    finished_run = uuid4()
    stop = threading.Event()
    ready = threading.Event()

    def _run_handler(message: RequestedMessage) -> HandleOutcome:
        raise AssertionError("Agent Run 스트림에는 아무것도 보내지 않았습니다")

    def _ingestion_handler(message: IngestionRequestedMessage) -> HandleIngestionOutcome:
        raise AssertionError("적재 스트림에는 아무것도 보내지 않았습니다")

    thread = threading.Thread(
        target=lambda: serve(
            settings,
            stop=stop,
            make_client=lambda: redis_client,
            on_ready=ready.set,
            handler=_run_handler,
            ingestion_handler=_ingestion_handler,
            resume=resume,
        ),
        daemon=True,
    )
    thread.start()
    try:
        assert ready.wait(_STOP_JOIN_TIMEOUT), "serve 가 준비되지 않았습니다"
        redis_client.xadd(
            settings.worker_status_stream,
            {
                "run_id": str(finished_run),
                "seq": "3",
                "status": "succeeded",
                "at": "2026-10-14T12:00:00+00:00",
            },
        )

        assert wait_until(lambda: resume.finished == [finished_run], timeout=_STOP_JOIN_TIMEOUT), (
            "빠른 경로 소비자 스레드가 뜨지 않았습니다"
        )
        assert wait_until(lambda: resume.sweeps >= 2, timeout=_STOP_JOIN_TIMEOUT), (
            "스위퍼 스레드가 뜨지 않았거나 주기마다 돌지 않습니다"
        )
    finally:
        stop.set()
        thread.join(_STOP_JOIN_TIMEOUT * 2)


def test_serve_with_the_production_workflow_handler_advances_a_requested_run(
    migrated_database: None,
    db_host_port: tuple[str, int],
    redis_client: Redis,
    admin_connection_factory: Callable[[], psycopg.Connection],
) -> None:
    """`workflow_handler` 를 주입하지 않은 `serve()` 가 요청 스트림의 메시지를 실제로 끝까지
    전진시킨다 - Workflow 소비자 스레드가 안 뜨면 `succeeded` 에 닿지 못해 이 테스트가 실패한다."""
    settings = Settings(
        database_url=_data_url(db_host_port),
        worker_consumer=f"test-consumer-{uuid4()}",
        worker_heartbeat_seconds=1,
    )
    run_id, version_id = declare_workflow_run(
        admin_connection_factory,
        (Node("start", NodeKind.START), Node("end", NodeKind.END)),
        (Edge("start", "end"),),
    )
    redis_client.xadd(
        settings.workflow_stream,
        {
            "workflow_run_id": str(run_id),
            "workflow_version_id": str(version_id),
            "traceparent": "",
        },
    )

    stop = threading.Event()
    ready = threading.Event()

    def _run_handler(message: RequestedMessage) -> HandleOutcome:
        raise AssertionError("Agent Run 스트림에는 아무것도 보내지 않았습니다")

    def _ingestion_handler(message: IngestionRequestedMessage) -> HandleIngestionOutcome:
        raise AssertionError("적재 스트림에는 아무것도 보내지 않았습니다")

    thread = threading.Thread(
        target=lambda: serve(
            settings,
            stop=stop,
            make_client=lambda: redis_client,
            on_ready=ready.set,
            handler=_run_handler,
            ingestion_handler=_ingestion_handler,
        ),
        daemon=True,
    )
    thread.start()
    try:
        assert ready.wait(_STOP_JOIN_TIMEOUT), "serve 가 준비되지 않았습니다"

        def _status() -> str | None:
            conn = admin_connection_factory()
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT status::text FROM data.workflow_run_executions"
                        " WHERE workflow_run_id = %s",
                        (run_id,),
                    )
                    row = cur.fetchone()
            finally:
                conn.close()
            return None if row is None else str(row[0])

        assert wait_until(lambda: _status() == "succeeded", timeout=10.0), (
            "프로덕션 조립이 Workflow 요청을 처리하지 않았습니다"
        )
        assert wait_until(
            lambda: (
                redis_client.xpending(settings.workflow_stream, settings.workflow_group)["pending"]
                == 0
            ),
            timeout=_STOP_JOIN_TIMEOUT,
        ), "처리한 요청은 ack 되어야 합니다"
    finally:
        stop.set()
        thread.join(_STOP_JOIN_TIMEOUT * 2)
