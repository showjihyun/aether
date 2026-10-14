"""spec 0005 2.9 개정 2, 2.10 (P4-2a A1): `WorkflowRunStatusConsumer` 의 읽기·ack 규칙 — 컨테이너
없이 최소 스트림 fake 로 증명합니다(`status_consumer.py` 와 같은 모양, 실제 Redis 위의 왕복은
`test_workflow_run_streams_integration.py`).

규칙: 자기 PEL 을 먼저 비우고(`XREADGROUP … 0`) 새 메시지(`">"`)로 넘어갑니다. 파싱 실패는
`apply` 를 부르지 않고 WARNING 과 함께 즉시 ack, 파싱된 메시지는 `apply` 의 반환값(적용
`True` / 무시 `False`)과 무관하게 ack 합니다.
"""

from __future__ import annotations

from threading import Event
from uuid import UUID, uuid4

import pytest
from aether_api.adapters.inbound.stream.workflow_run_status_consumer import (
    WorkflowRunStatusConsumer,
)
from aether_api.domain.workflow_run_status_message import WorkflowRunStatusMessage
from aether_workflow.domain.run_status import WorkflowRunStatus
from redis import Redis

from tests.support.stream_fakes import FakeStreamClient

_STREAM = "aether:workflow_runs:status"
_GROUP = "aether-api"
_AT = "2026-01-01T00:00:00+00:00"


class _RecordingApply:
    def __init__(self, *, result: bool = True) -> None:
        self.calls: list[WorkflowRunStatusMessage] = []
        self._result = result

    def __call__(self, message: WorkflowRunStatusMessage) -> bool:
        self.calls.append(message)
        return self._result


def _fields(run_id: UUID, **extra: str) -> dict[str, str]:
    return {"workflow_run_id": str(run_id), "seq": "1", "status": "running", "at": _AT, **extra}


def _run(client: FakeStreamClient, apply: _RecordingApply, stop: Event) -> None:
    consumer = WorkflowRunStatusConsumer(
        client,  # type: ignore[arg-type]
        apply,
        stream=_STREAM,
        group=_GROUP,
        consumer="api-a",
    )
    consumer.run_until(stop)


def test_parsed_message_is_applied_and_acked() -> None:
    stop = Event()
    run_id = uuid4()
    client = FakeStreamClient(stop, pending=[], new=[("1-0", _fields(run_id, current_node_id="s"))])
    apply = _RecordingApply()

    _run(client, apply, stop)

    assert [m.workflow_run_id for m in apply.calls] == [run_id]
    assert apply.calls[0].status == WorkflowRunStatus.RUNNING
    assert apply.calls[0].current_node_id == "s"
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
        _run(client, apply, stop)

    assert apply.calls == []
    assert client.acked == ["1-0", "2-0"]
    assert sum(1 for r in caplog.records if r.levelname == "WARNING") == 2


def test_ignored_message_is_still_acked() -> None:
    """`apply` 가 `False`(낮거나 같은 seq) 를 돌려줘도 ack 한다 — 멱등 무시."""
    stop = Event()
    client = FakeStreamClient(stop, pending=[], new=[("1-0", _fields(uuid4()))])
    apply = _RecordingApply(result=False)

    _run(client, apply, stop)

    assert len(apply.calls) == 1
    assert client.acked == ["1-0"]


def test_own_pending_entries_are_processed_before_new_messages() -> None:
    stop = Event()
    first, second = uuid4(), uuid4()
    client = FakeStreamClient(
        stop, pending=[("1-0", _fields(first))], new=[("2-0", _fields(second))]
    )
    apply = _RecordingApply()

    _run(client, apply, stop)

    assert [m.workflow_run_id for m in apply.calls] == [first, second]
    assert client.group_args[0] == (_GROUP, "api-a", "0")


def test_default_stream_and_group_are_the_contract_names() -> None:
    """스트림 계약(plan 부록 A): 상태 스트림 `aether:workflow_runs:status`, group `aether-api`."""
    consumer = WorkflowRunStatusConsumer(Redis(), _RecordingApply())  # 연결은 열지 않는다

    assert consumer.stream == _STREAM
    assert consumer.group == _GROUP
