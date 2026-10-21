"""spec 0007 2.3, D-3, D-4, R-5 (P5-1): 노드 실행 투영 -- worker 통지부터 투영 표까지, 실제
PostgreSQL + Redis.

`api-integration`. 증명하는 것:

1. **worker 통지 -> 투영 표** 한 번: worker 의 `RedisWorkflowNodeStatusNotifier` 가 쓴 메시지를
   api 의 `WorkflowNodeStatusConsumer` 가 읽어 `control.workflow_node_states` 에 넣는다.
   계약이 두 번 구현되므로(AR-7: 서로 import 하지 않는 필드 이름) 이 왕복만이 맞물림을 판정한다.
2. 같은 키의 **낮은 `status_seq` 는 표를 바꾸지 못한다**(SQL 의 `WHERE status_seq < excluded`).
   같은 Run 의 다른 노드는 영향이 없다.
3. 루프에서 노드가 다시 `running` 이 되면 이전 회차의 `finished_at`·`failure_reason` 이 지워진다.
4. 없는 Workflow Run 의 메시지는 예외 없이 무시되고(`False`) 표가 비어 있다.
"""

from __future__ import annotations

import threading
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

import psycopg
import pytest
from aether_api.adapters.inbound.stream.status_consumer import ensure_group
from aether_api.adapters.inbound.stream.workflow_node_status_consumer import (
    WorkflowNodeStatusConsumer,
)
from aether_api.adapters.outbound.db.workflow_node_state_projection_store import (
    PostgresWorkflowNodeStateProjectionStore,
)
from aether_api.application.usecases.apply_workflow_node_status import (
    ApplyWorkflowNodeStatusUseCase,
)
from aether_api.domain.workflow_node_status_message import (
    WorkflowNodeStatusMessage as ApiNodeStatusMessage,
)
from aether_workflow.adapters.outbound.redis.workflow_node_status_notifier import (
    RedisWorkflowNodeStatusNotifier,
)
from aether_workflow.application.ports.outbound.workflow_node_status_notifier import (
    WorkflowNodeStatusMessage,
)
from aether_workflow.domain.failure import WorkflowFailureReason
from aether_workflow.domain.node import NodeKind
from aether_workflow.domain.node_execution import NodeExecutionStatus
from redis import Redis

from tests.support.waiting import wait_until

pytestmark = pytest.mark.integration

_Factory = Callable[[], psycopg.Connection]
_STREAM = "aether:workflow_node_states:status"
_GROUP = "aether-api"
_T0 = datetime(2026, 10, 21, 12, 0, tzinfo=UTC)
_T1 = datetime(2026, 10, 21, 12, 5, tzinfo=UTC)


def _seed_run(conn: psycopg.Connection) -> uuid.UUID:
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO control.workflows (name) VALUES (%s) RETURNING id", (f"wf-{uuid.uuid4()}",)
        )
        row = cur.fetchone()
        assert row is not None
        cur.execute(
            "INSERT INTO control.workflow_versions (workflow_id, version, nodes, edges) "
            "VALUES (%s, 1, '[]', '[]') RETURNING id",
            (row[0],),
        )
        version = cur.fetchone()
        assert version is not None
        cur.execute(
            "INSERT INTO control.workflow_runs (workflow_version_id) VALUES (%s) RETURNING id",
            (version[0],),
        )
        run = cur.fetchone()
        assert run is not None
        run_id: uuid.UUID = run[0]
    conn.commit()
    return run_id


def _seeded(admin_connection_factory: _Factory) -> uuid.UUID:
    admin = admin_connection_factory()
    try:
        return _seed_run(admin)
    finally:
        admin.close()


def _message(
    run_id: uuid.UUID, node_id: str, status: NodeExecutionStatus, seq: int, **extra: Any
) -> WorkflowNodeStatusMessage:
    return WorkflowNodeStatusMessage(
        workflow_run_id=run_id,
        node_id=node_id,
        kind=NodeKind.AGENT,
        status=status,
        status_seq=seq,
        **extra,
    )


def _rows(factory: _Factory, run_id: uuid.UUID) -> dict[str, tuple[Any, ...]]:
    conn = factory()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT node_id, kind, status::text, status_seq, started_at, finished_at, "
                "failure_reason FROM control.workflow_node_states "
                "WHERE workflow_run_id = %s",
                (run_id,),
            )
            return {r[0]: tuple(r[1:]) for r in cur.fetchall()}
    finally:
        conn.close()


def _drain(
    redis_client: Redis,
    control_connection_factory: _Factory,
    messages: list[WorkflowNodeStatusMessage],
) -> None:
    """worker 의 notifier 로 쓰고 api 의 소비자가 다 읽을 때까지 돌린다."""
    ensure_group(redis_client, _STREAM, _GROUP)
    notifier = RedisWorkflowNodeStatusNotifier(redis_client)
    for message in messages:
        notifier.notify(message)
    consumer = WorkflowNodeStatusConsumer(
        redis_client,
        ApplyWorkflowNodeStatusUseCase(
            PostgresWorkflowNodeStateProjectionStore(control_connection_factory)
        ),
        stream=_STREAM,
        group=_GROUP,
        block_ms=100,
    )
    stop = threading.Event()
    thread = threading.Thread(target=consumer.run_until, args=(stop,), daemon=True)
    thread.start()
    try:

        def _all_acked() -> bool:
            pending: Any = redis_client.xpending(_STREAM, _GROUP)
            info: Any = redis_client.xinfo_groups(_STREAM)[0]
            return int(pending["pending"]) == 0 and int(info["lag"] or 0) == 0

        assert wait_until(_all_acked, timeout=10.0), "소비자가 메시지를 다 읽지 못했습니다"
    finally:
        stop.set()
        thread.join(5.0)


def test_worker_notification_reaches_the_projection_table(
    redis_client: Redis,
    control_connection_factory: _Factory,
    admin_connection_factory: _Factory,
) -> None:
    """R-5: 통지 -> 스트림 -> 소비자 -> 표. 새 노드가 들어가고, 파킹은 상태만 바꾸고, 끝나면
    시각·사유가 채워진다."""
    run_id = _seeded(admin_connection_factory)

    _drain(
        redis_client,
        control_connection_factory,
        [
            _message(run_id, "a", NodeExecutionStatus.RUNNING, 2, started_at=_T0),
            _message(run_id, "a", NodeExecutionStatus.WAITING_RUN, 3),
            _message(
                run_id,
                "a",
                NodeExecutionStatus.FAILED,
                5,
                finished_at=_T1,
                failure_reason=WorkflowFailureReason.AGENT_RUN_FAILED,
            ),
        ],
    )

    assert _rows(control_connection_factory, run_id) == {
        "a": ("AGENT", "failed", 5, _T0, _T1, "agent_run_failed")
    }


def test_a_lower_status_seq_for_the_same_key_does_not_change_the_row(
    redis_client: Redis,
    control_connection_factory: _Factory,
    admin_connection_factory: _Factory,
) -> None:
    """R-5: 늦게 온 낮은(또는 같은) `status_seq` 는 표를 바꾸지 못한다. 키가 `(run, node)` 라 다른
    노드의 높은 seq 는 막지 않는다."""
    run_id = _seeded(admin_connection_factory)

    _drain(
        redis_client,
        control_connection_factory,
        [
            _message(run_id, "a", NodeExecutionStatus.SUCCEEDED, 7, finished_at=_T1),
            _message(run_id, "a", NodeExecutionStatus.RUNNING, 4, started_at=_T0),
            _message(run_id, "a", NodeExecutionStatus.RUNNING, 7),
            _message(run_id, "b", NodeExecutionStatus.RUNNING, 3, started_at=_T0),
        ],
    )

    rows = _rows(control_connection_factory, run_id)
    assert rows["a"] == ("AGENT", "succeeded", 7, None, _T1, None)
    assert rows["b"] == ("AGENT", "running", 3, _T0, None, None)


def test_rerunning_a_node_clears_the_previous_iterations_end(
    redis_client: Redis,
    control_connection_factory: _Factory,
    admin_connection_factory: _Factory,
) -> None:
    """루프: 같은 노드가 다시 `running` 이 되면 이전 회차의 `finished_at`·`failure_reason` 이 남지
    않는다. `started_at` 은 새 회차의 값으로 바뀐다."""
    run_id = _seeded(admin_connection_factory)

    _drain(
        redis_client,
        control_connection_factory,
        [
            _message(
                run_id,
                "a",
                NodeExecutionStatus.FAILED,
                3,
                started_at=_T0,
                finished_at=_T0,
                failure_reason=WorkflowFailureReason.AGENT_RUN_FAILED,
            ),
            _message(run_id, "a", NodeExecutionStatus.RUNNING, 6, started_at=_T1),
        ],
    )

    assert _rows(control_connection_factory, run_id)["a"] == (
        "AGENT",
        "running",
        6,
        _T1,
        None,
        None,
    )


def test_a_message_for_an_unknown_workflow_run_is_ignored(
    control_connection_factory: _Factory,
) -> None:
    """없는 Workflow Run: 예외 없이 무시(`False`)하고 표에 행이 생기지 않는다."""
    store = PostgresWorkflowNodeStateProjectionStore(control_connection_factory)
    missing = uuid.uuid4()

    applied = store.apply_status(
        ApiNodeStatusMessage(
            workflow_run_id=missing,
            node_id="a",
            kind="AGENT",
            status=NodeExecutionStatus.RUNNING,
            status_seq=1,
        )
    )

    assert applied is False
    assert _rows(control_connection_factory, missing) == {}
