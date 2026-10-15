"""spec 0005 2.9 개정 2, 2.10: `RedisWorkflowEventSink`·`RedisWorkflowStatusNotifier` 의 포트 계약 -
실제 Redis 위에서 검증합니다. `test_redis_adapters.py`(Agent Run)와 같은 계약이지만 **다른 키**를
씁니다(D-13).

`WorkflowEventSink` 계약의 핵심은 **같은 `seq` 의 재발행은 성공**입니다 - 그 밖의
`ResponseError` 는 그대로 전파해야 합니다.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from aether_workflow.adapters.outbound.redis.workflow_event_sink import RedisWorkflowEventSink
from aether_workflow.adapters.outbound.redis.workflow_status_notifier import (
    RedisWorkflowStatusNotifier,
)
from aether_workflow.application.ports.outbound.workflow_status_notifier import (
    WorkflowStatusMessage,
)
from aether_workflow.domain.events import WorkflowEvent, WorkflowEventType
from aether_workflow.domain.failure import WorkflowFailureReason
from aether_workflow.domain.run_status import WorkflowRunStatus
from redis import Redis
from redis.exceptions import ResponseError

pytestmark = pytest.mark.integration

_AT = datetime(2026, 10, 14, 12, 0, tzinfo=UTC)


def _event(
    run_id: uuid.UUID, seq: int, type_: WorkflowEventType = "workflow.status"
) -> WorkflowEvent:
    return WorkflowEvent(
        workflow_run_id=run_id, seq=seq, at=_AT, type=type_, payload={"status": "running"}
    )


def _entries(client: Redis, stream: str) -> list[tuple[str, dict[str, str]]]:
    raw = client.xrange(stream, min="-", max="+")
    assert raw is not None
    return [(str(i), {str(k): str(v) for k, v in (f or {}).items()}) for i, f in raw]


def test_event_is_appended_with_explicit_id_seq_dash_zero(redis_client: Redis) -> None:
    run_id = uuid.uuid4()
    sink = RedisWorkflowEventSink(redis_client)

    sink.publish(_event(run_id, 1))
    sink.publish(_event(run_id, 2, "node.started"))

    entries = _entries(redis_client, f"aether:workflow_runs:{run_id}:events")
    assert [entry_id for entry_id, _ in entries] == ["1-0", "2-0"]
    restored = WorkflowEvent.model_validate_json(entries[1][1]["data"])
    assert restored.type == "node.started"
    assert restored.workflow_run_id == run_id


def test_republishing_the_same_seq_is_absorbed_as_success(redis_client: Redis) -> None:
    run_id = uuid.uuid4()
    sink = RedisWorkflowEventSink(redis_client)
    sink.publish(_event(run_id, 1))
    sink.publish(_event(run_id, 2))

    sink.publish(_event(run_id, 2))
    sink.publish(_event(run_id, 1))

    assert len(_entries(redis_client, f"aether:workflow_runs:{run_id}:events")) == 2


def test_other_response_errors_are_not_swallowed(redis_client: Redis) -> None:
    run_id = uuid.uuid4()
    redis_client.set(f"aether:workflow_runs:{run_id}:events", "not-a-stream")

    with pytest.raises(ResponseError):
        RedisWorkflowEventSink(redis_client).publish(_event(run_id, 1))


def test_stream_expires_only_after_workflow_finished(redis_client: Redis) -> None:
    run_id = uuid.uuid4()
    key = f"aether:workflow_runs:{run_id}:events"
    sink = RedisWorkflowEventSink(redis_client, ttl_seconds=100)

    sink.publish(_event(run_id, 1))
    assert redis_client.ttl(key) == -1

    sink.publish(_event(run_id, 2, "workflow.finished"))
    assert 0 < redis_client.ttl(key) <= 100


def test_maxlen_trims_the_stream_approximately(redis_client: Redis) -> None:
    run_id = uuid.uuid4()
    sink = RedisWorkflowEventSink(redis_client, maxlen=5)

    for seq in range(1, 301):
        sink.publish(_event(run_id, seq))

    assert redis_client.xlen(f"aether:workflow_runs:{run_id}:events") < 300


def test_status_message_fields_and_absent_optionals(redis_client: Redis) -> None:
    """A1 계약: 값이 없는 선택 필드는 필드 자체를 보내지 않는다."""
    run_id = uuid.uuid4()
    notifier = RedisWorkflowStatusNotifier(redis_client)

    notifier.notify(
        WorkflowStatusMessage(
            workflow_run_id=run_id, seq=1, status=WorkflowRunStatus.RUNNING, at=_AT
        )
    )
    notifier.notify(
        WorkflowStatusMessage(
            workflow_run_id=run_id,
            seq=6,
            status=WorkflowRunStatus.FAILED,
            at=_AT,
            current_node_id="a",
            started_at=_AT,
            finished_at=_AT,
            failure_reason=WorkflowFailureReason.UNSUPPORTED_NODE_KIND,
        )
    )
    child = uuid.uuid4()
    notifier.notify(
        WorkflowStatusMessage(
            workflow_run_id=run_id,
            seq=5,
            status=WorkflowRunStatus.WAITING_RUN,
            at=_AT,
            current_node_id="a",
            waiting_run_id=child,
        )
    )

    first, second, parked = (
        fields for _, fields in _entries(redis_client, "aether:workflow_runs:status")
    )
    assert first == {
        "workflow_run_id": str(run_id),
        "seq": "1",
        "status": "running",
        "at": _AT.isoformat(),
    }
    assert second == {
        "workflow_run_id": str(run_id),
        "seq": "6",
        "status": "failed",
        "at": _AT.isoformat(),
        "current_node_id": "a",
        "started_at": _AT.isoformat(),
        "finished_at": _AT.isoformat(),
        "failure_reason": "unsupported_node_kind",
    }
    assert parked == {
        "workflow_run_id": str(run_id),
        "seq": "5",
        "status": "waiting_run",
        "at": _AT.isoformat(),
        "current_node_id": "a",
        "waiting_run_id": str(child),
    }, "파킹 통지는 기다리는 자식 Run 을 싣는다(R-13) - 다른 통지에는 이 필드가 없다"


def test_status_message_carries_the_awaited_node_execution_only_when_present(
    redis_client: Redis,
) -> None:
    """spec 0005 2.6 개정 5 (1), R-12 (P4-4): `waiting_approval` 통지는 기다리는 노드 실행의 id 를
    `waiting_node_execution_id` 로 싣고, 없으면 필드 자체를 보내지 않는다(A1 계약)."""
    run_id = uuid.uuid4()
    awaited = uuid.uuid4()
    notifier = RedisWorkflowStatusNotifier(redis_client)

    notifier.notify(
        WorkflowStatusMessage(
            workflow_run_id=run_id,
            seq=4,
            status=WorkflowRunStatus.WAITING_APPROVAL,
            at=_AT,
            current_node_id="gate",
            waiting_node_execution_id=awaited,
        )
    )
    notifier.notify(
        WorkflowStatusMessage(
            workflow_run_id=run_id, seq=5, status=WorkflowRunStatus.RUNNING, at=_AT
        )
    )

    parked, running = (
        fields for _, fields in _entries(redis_client, "aether:workflow_runs:status")
    )
    assert parked == {
        "workflow_run_id": str(run_id),
        "seq": "4",
        "status": "waiting_approval",
        "at": _AT.isoformat(),
        "current_node_id": "gate",
        "waiting_node_execution_id": str(awaited),
    }
    assert "waiting_node_execution_id" not in running
