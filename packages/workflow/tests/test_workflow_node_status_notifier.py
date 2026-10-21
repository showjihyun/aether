"""spec 0007 2.3, D-3, D-4 (P5-1): `RedisWorkflowNodeStatusNotifier` 의 스트림 계약 -- 실제 Redis.

계약: `aether:workflow_node_states:status` 에 필드를 문자열로 `XADD`. 값이 없는 선택 필드는
**필드 자체를 보내지 않는다**(A1 계약). 노드 출력은 필드에 없다(D-4).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
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

pytestmark = pytest.mark.integration

_AT = datetime(2026, 10, 21, 12, 0, tzinfo=UTC)
_STREAM = "aether:workflow_node_states:status"


def _entries(client: Redis) -> list[dict[str, str]]:
    raw = client.xrange(_STREAM, min="-", max="+")
    assert raw is not None
    return [{str(k): str(v) for k, v in (fields or {}).items()} for _, fields in raw]


def test_required_fields_only_when_optionals_are_absent(redis_client: Redis) -> None:
    run_id = uuid.uuid4()
    notifier = RedisWorkflowNodeStatusNotifier(redis_client)

    notifier.notify(
        WorkflowNodeStatusMessage(
            workflow_run_id=run_id,
            node_id="a",
            kind=NodeKind.AGENT,
            status=NodeExecutionStatus.WAITING_RUN,
            status_seq=3,
        )
    )

    assert _entries(redis_client) == [
        {
            "workflow_run_id": str(run_id),
            "node_id": "a",
            "kind": "AGENT",
            "status": "waiting_run",
            "status_seq": "3",
        }
    ]


def test_optional_fields_are_sent_only_when_present(redis_client: Redis) -> None:
    run_id = uuid.uuid4()
    notifier = RedisWorkflowNodeStatusNotifier(redis_client)

    notifier.notify(
        WorkflowNodeStatusMessage(
            workflow_run_id=run_id,
            node_id="a",
            kind=NodeKind.AGENT,
            status=NodeExecutionStatus.FAILED,
            status_seq=9,
            started_at=_AT,
            finished_at=_AT,
            failure_reason=WorkflowFailureReason.AGENT_RUN_FAILED,
        )
    )

    (fields,) = _entries(redis_client)
    assert fields == {
        "workflow_run_id": str(run_id),
        "node_id": "a",
        "kind": "AGENT",
        "status": "failed",
        "status_seq": "9",
        "started_at": _AT.isoformat(),
        "finished_at": _AT.isoformat(),
        "failure_reason": "agent_run_failed",
    }
    assert "output" not in fields


def test_default_stream_is_not_the_run_status_stream(redis_client: Redis) -> None:
    """기존 `aether:workflow_runs:status`(소비자 둘)를 건드리지 않는다."""
    notifier = RedisWorkflowNodeStatusNotifier(redis_client)
    notifier.notify(
        WorkflowNodeStatusMessage(
            workflow_run_id=uuid.uuid4(),
            node_id="a",
            kind=NodeKind.START,
            status=NodeExecutionStatus.RUNNING,
            status_seq=1,
        )
    )

    assert redis_client.xlen("aether:workflow_runs:status") == 0
    assert redis_client.xlen(_STREAM) == 1
