"""spec 0007 2.3, D-3, D-4, R-5 (P5-1): `WorkflowNodeStatusConsumer` -- 컨테이너 없이 최소 스트림
fake 로 증명합니다(`workflow_run_status_consumer.py` 와 같은 모양, PostgreSQL 위의 `status_seq`
단조 규칙은 `test_workflow_node_projection_integration.py`).

규칙: 자기 PEL 을 먼저 비우고 새 메시지로 넘어갑니다. 파싱 실패는 `apply` 를 부르지 않고 WARNING
과 함께 즉시 ack. 적용 여부와 무관하게 ack. **모르는 필드는 무시합니다**(앞으로 필드가 늘어도 깨지지
않습니다).
"""

from __future__ import annotations

from threading import Event
from uuid import UUID, uuid4

import pytest
from aether_api.adapters.inbound.stream.workflow_node_status_consumer import (
    WorkflowNodeStatusConsumer,
)
from aether_api.application.usecases.apply_workflow_node_status import (
    ApplyWorkflowNodeStatusUseCase,
)
from aether_api.domain.workflow_node_status_message import WorkflowNodeStatusMessage
from aether_workflow.domain.node_execution import NodeExecutionStatus
from redis import Redis

from tests.support.stream_fakes import FakeStreamClient

_STREAM = "aether:workflow_node_states:status"
_GROUP = "aether-api"
_AT = "2026-01-01T00:00:00+00:00"


class _RecordingApply:
    def __init__(self, *, result: bool = True) -> None:
        self.calls: list[WorkflowNodeStatusMessage] = []
        self._result = result

    def __call__(self, message: WorkflowNodeStatusMessage) -> bool:
        self.calls.append(message)
        return self._result


class _FakeNodeProjectionStore:
    """`status_seq` 단조 규칙을 흉내 내는 인메모리 투영(실제 규칙은 SQL 이 소유하고 통합 테스트가
    증명한다)."""

    def __init__(self) -> None:
        self.rows: dict[tuple[UUID, str], WorkflowNodeStatusMessage] = {}

    def apply_status(self, message: WorkflowNodeStatusMessage) -> bool:
        key = (message.workflow_run_id, message.node_id)
        existing = self.rows.get(key)
        if existing is not None and existing.status_seq >= message.status_seq:
            return False
        self.rows[key] = message
        return True


def _fields(run_id: UUID, **extra: str) -> dict[str, str]:
    return {
        "workflow_run_id": str(run_id),
        "node_id": "a",
        "kind": "AGENT",
        "status": "running",
        "status_seq": "1",
        **extra,
    }


def _run(client: FakeStreamClient, apply: _RecordingApply | ApplyWorkflowNodeStatusUseCase) -> None:
    consumer = WorkflowNodeStatusConsumer(
        client,  # type: ignore[arg-type]
        apply,
        stream=_STREAM,
        group=_GROUP,
        consumer="api-a",
    )
    consumer.run_until(client._stop)  # noqa: SLF001 - fake 가 stop 을 쥐고 있다


def test_a_new_node_is_put_into_the_projection_and_acked() -> None:
    """R-5: 처음 보는 `(workflow_run_id, node_id)` 는 투영에 들어간다."""
    stop = Event()
    run_id = uuid4()
    client = FakeStreamClient(
        stop,
        pending=[],
        new=[("1-0", _fields(run_id, started_at=_AT))],
    )
    store = _FakeNodeProjectionStore()

    _run(client, ApplyWorkflowNodeStatusUseCase(store))

    row = store.rows[(run_id, "a")]
    assert (row.kind, row.status, row.status_seq) == ("AGENT", NodeExecutionStatus.RUNNING, 1)
    assert row.started_at is not None
    assert client.acked == ["1-0"]


def test_a_late_message_for_the_same_key_is_discarded_but_acked() -> None:
    """R-5: 같은 키의 낮은 `status_seq` 는 버린다 -- 다른 노드의 높은 seq 는 영향을 주지 않는다."""
    stop = Event()
    run_id = uuid4()
    client = FakeStreamClient(
        stop,
        pending=[],
        new=[
            ("1-0", _fields(run_id, status="succeeded", status_seq="5")),
            ("2-0", _fields(run_id, status="running", status_seq="2")),
            ("3-0", {**_fields(run_id, status_seq="1"), "node_id": "b"}),
        ],
    )
    store = _FakeNodeProjectionStore()

    _run(client, ApplyWorkflowNodeStatusUseCase(store))

    assert store.rows[(run_id, "a")].status == NodeExecutionStatus.SUCCEEDED
    assert store.rows[(run_id, "b")].status_seq == 1  # 노드 단위 비교: a 의 5 가 b 를 막지 않는다
    assert client.acked == ["1-0", "2-0", "3-0"]


def test_unknown_fields_are_ignored() -> None:
    """앞으로 필드가 늘어도 깨지지 않는다: 모르는 필드가 있어도 파싱돼 `apply` 에 간다."""
    stop = Event()
    run_id = uuid4()
    client = FakeStreamClient(
        stop,
        pending=[],
        new=[("1-0", _fields(run_id, iteration="3", future_field="x"))],
    )
    apply = _RecordingApply()

    _run(client, apply)

    assert [m.workflow_run_id for m in apply.calls] == [run_id]
    assert not hasattr(apply.calls[0], "future_field")
    assert client.acked == ["1-0"]


def test_malformed_message_is_acked_without_calling_apply(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """독약 메시지: WARNING 과 함께 즉시 ack, `apply` 는 부르지 않는다."""
    stop = Event()
    client = FakeStreamClient(
        stop,
        pending=[],
        new=[
            ("1-0", {"workflow_run_id": str(uuid4())}),
            ("2-0", {**_fields(uuid4()), "status": "timed_out"}),
        ],
    )
    apply = _RecordingApply()

    with caplog.at_level("WARNING"):
        _run(client, apply)

    assert apply.calls == []
    assert client.acked == ["1-0", "2-0"]
    assert sum(1 for r in caplog.records if r.levelname == "WARNING") == 2


def test_own_pending_entries_are_processed_before_new_messages() -> None:
    stop = Event()
    first, second = uuid4(), uuid4()
    client = FakeStreamClient(
        stop, pending=[("1-0", _fields(first))], new=[("2-0", _fields(second))]
    )
    apply = _RecordingApply()

    _run(client, apply)

    assert [m.workflow_run_id for m in apply.calls] == [first, second]
    assert client.group_args[0] == (_GROUP, "api-a", "0")


def test_default_stream_and_group_are_the_contract_names() -> None:
    """스트림 계약: 노드 상태 스트림 `aether:workflow_node_states:status`, group `aether-api`
    (기존 `aether:workflow_runs:status` 와 **다른 스트림** -- 그 스트림의 소비자 둘을 건드리지
    않는다, plan 0007 P5-1)."""
    consumer = WorkflowNodeStatusConsumer(Redis(), _RecordingApply())  # 연결은 열지 않는다
    assert consumer.stream == _STREAM
    assert consumer.group == _GROUP
