"""spec 0005 2.1, 2.9 개정 2 (P4-2a A): worker 의 **프로덕션 조립**이 Workflow 소비자를 실제로
띄우는지.

`test_workflow_executor_integration.py` 는 손으로 반복한 조립이 올바른지 증명합니다. 여기서는
"worker 의 실제 조립(`_build_production_workflow_handler`, `serve()`)이 그것을 꽂는가" 만 봅니다.
꽂지 않으면(handler 가 없거나, 스레드가 안 뜨거나, 어댑터가 빠지면) 요청이 영원히 처리되지
않고 조용히 `queued` 로 남습니다 - 이 파일이 그 침묵을 실패로 바꿉니다.
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from uuid import uuid4

import psycopg
import pytest
from aether_worker.application.ports.inbound.handle_ingestion_requested import (
    HandleIngestionOutcome,
    IngestionRequestedMessage,
)
from aether_worker.application.ports.inbound.handle_run_requested import (
    HandleOutcome,
    RequestedMessage,
)
from aether_worker.main import _build_production_workflow_handler, serve
from aether_worker.settings import Settings
from aether_workflow.adapters.outbound.db.workflow_run_declaration_reader import (
    PostgresWorkflowRunDeclarationReader,
)
from aether_workflow.adapters.outbound.db.workflow_run_state_store import (
    PostgresWorkflowRunStateStore,
)
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
    assert advance._owner == settings.worker_consumer
    assert advance._lease_ttl_seconds == settings.worker_lease_seconds


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
