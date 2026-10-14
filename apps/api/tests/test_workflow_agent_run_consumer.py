"""spec 0005 2.5 개정 3 (P4-2a B1): `WorkflowAgentRunConsumer` 의 읽기·ack 규칙 -- 컨테이너 없이
최소 스트림 fake 로 증명합니다(`workflow_run_status_consumer` 와 같은 모양, 실제 Redis 위의 왕복은
`test_workflow_agent_run_integration.py`).

규칙: 자기 PEL 을 먼저 비우고(`XREADGROUP ... 0`) 새 메시지(`">"`)로 넘어갑니다. 파싱 실패는
`declare` 를 부르지 않고 WARNING 과 함께 즉시 ack. 선언이 끝나면(`True`/`False` 무관) ack.
**선언이 예외를 던지면 삼키지 않고 올리며 ack 하지 않습니다** -- 없는 Version 은 실행기가 걸러
내므로 여기서 오는 FK 위반은 평범한 입력이 아니라 버그입니다.
"""

from __future__ import annotations

from threading import Event
from uuid import UUID, uuid4

import pytest
from aether_api.adapters.inbound.stream.workflow_agent_run_consumer import (
    WorkflowAgentRunConsumer,
)
from aether_api.domain.workflow_agent_run_request import WorkflowAgentRunRequest
from redis import Redis

from tests.support.stream_fakes import FakeStreamClient

_STREAM = "aether:workflow:agent_runs:requested"
_GROUP = "aether-api"


class _RecordingDeclare:
    def __init__(self, *, result: bool = True, error: Exception | None = None) -> None:
        self.calls: list[WorkflowAgentRunRequest] = []
        self._result = result
        self._error = error

    def __call__(self, request: WorkflowAgentRunRequest) -> bool:
        self.calls.append(request)
        if self._error is not None:
            raise self._error
        return self._result


def _fields(run_id: UUID, **extra: str) -> dict[str, str]:
    return {
        "agent_run_id": str(run_id),
        "agent_version_id": str(uuid4()),
        "input": "do it",
        "traceparent": "",
        **extra,
    }


def _run(client: FakeStreamClient, declare: _RecordingDeclare, stop: Event) -> None:
    consumer = WorkflowAgentRunConsumer(
        client,  # type: ignore[arg-type]
        declare,
        stream=_STREAM,
        group=_GROUP,
        consumer="api-a",
    )
    consumer.run_until(stop)


def test_parsed_message_is_declared_and_acked() -> None:
    stop = Event()
    run_id = uuid4()
    client = FakeStreamClient(stop, pending=[], new=[("1-0", _fields(run_id))])
    declare = _RecordingDeclare()

    _run(client, declare, stop)

    assert [r.agent_run_id for r in declare.calls] == [run_id]
    assert declare.calls[0].input == "do it"
    assert client.acked == ["1-0"]


def test_malformed_message_is_acked_without_calling_declare(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """독약 메시지: WARNING 과 함께 즉시 ack, `declare` 는 부르지 않는다."""
    stop = Event()
    client = FakeStreamClient(
        stop,
        pending=[],
        new=[
            ("1-0", {"agent_run_id": str(uuid4())}),
            ("2-0", {**_fields(uuid4()), "agent_run_id": "not-a-uuid"}),
        ],
    )
    declare = _RecordingDeclare()

    with caplog.at_level("WARNING"):
        _run(client, declare, stop)

    assert declare.calls == []
    assert client.acked == ["1-0", "2-0"]
    assert sum(1 for r in caplog.records if r.levelname == "WARNING") == 2


def test_already_declared_message_is_still_acked() -> None:
    """`declare` 가 `False`(이미 있던 Run) 를 돌려줘도 ack 한다 -- 멱등 무시."""
    stop = Event()
    client = FakeStreamClient(stop, pending=[], new=[("1-0", _fields(uuid4()))])
    declare = _RecordingDeclare(result=False)

    _run(client, declare, stop)

    assert len(declare.calls) == 1
    assert client.acked == ["1-0"]


def test_declare_failure_is_raised_and_not_acked() -> None:
    """선언 실패(FK 위반 같은 버그)는 삼키지 않고 올리며, ack 하지 않아 PEL 에 남는다."""
    stop = Event()
    client = FakeStreamClient(stop, pending=[], new=[("1-0", _fields(uuid4()))])
    declare = _RecordingDeclare(error=RuntimeError("fk violation"))

    with pytest.raises(RuntimeError, match="fk violation"):
        _run(client, declare, stop)

    assert len(declare.calls) == 1
    assert client.acked == []


def test_own_pending_entries_are_processed_before_new_messages() -> None:
    stop = Event()
    first, second = uuid4(), uuid4()
    client = FakeStreamClient(
        stop, pending=[("1-0", _fields(first))], new=[("2-0", _fields(second))]
    )
    declare = _RecordingDeclare()

    _run(client, declare, stop)

    assert [r.agent_run_id for r in declare.calls] == [first, second]
    assert client.group_args[0] == (_GROUP, "api-a", "0")


def test_default_stream_and_group_are_the_contract_names() -> None:
    """스트림 계약(plan 부록 A): `aether:workflow:agent_runs:requested`, group `aether-api`."""
    consumer = WorkflowAgentRunConsumer(Redis(), _RecordingDeclare())  # 연결은 열지 않는다

    assert consumer.stream == _STREAM
    assert consumer.group == _GROUP
