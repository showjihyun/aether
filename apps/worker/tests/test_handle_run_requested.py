"""spec 0002 2.1, 2.4, D-10 (P1-5a): `HandleRunRequestedUseCase` — ack 규칙.

fake `ExecuteRun` 의 세 가지 동작(성공·`LeaseHeld`·선언 없음)에 따라 `HandleOutcome`
이 달라져야 합니다: 성공은 ack, `LeaseHeld` 는 ack 하지 않음(다음 `XAUTOCLAIM` 주기가
다시 봄), 선언 없음(`RuntimeError`)은 독약 메시지이므로 WARNING 로그를 남기고
ack 합니다 — PEL 에 영원히 남지 않게. `TraceContext.activate` 는 메시지의
`traceparent` 를 그대로 받아야 합니다(P1-8 이 실제로 씁니다).
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from uuid import UUID, uuid4

import pytest
from aether_runtime.domain.run import LeaseHeld, RunStatus
from aether_worker.application.ports.inbound.handle_run_requested import RequestedMessage
from aether_worker.application.usecases.handle_run_requested import HandleRunRequestedUseCase


class _FakeExecuteRun:
    def __init__(self, *, result: RunStatus | None = None, error: Exception | None = None) -> None:
        self._result = result
        self._error = error
        self.calls: list[UUID] = []

    def __call__(self, run_id: UUID) -> RunStatus:
        self.calls.append(run_id)
        if self._error is not None:
            raise self._error
        assert self._result is not None
        return self._result


class _FakeTraceContext:
    def __init__(self) -> None:
        self.activated: list[str | None] = []

    @contextmanager
    def activate(self, traceparent: str | None) -> Iterator[None]:
        self.activated.append(traceparent)
        yield


def _message(traceparent: str | None = "00-trace-01") -> RequestedMessage:
    return RequestedMessage(
        message_id="1-0",
        run_id=uuid4(),
        agent_version_id=uuid4(),
        traceparent=traceparent,
    )


def test_successful_execution_is_acked() -> None:
    execute_run = _FakeExecuteRun(result=RunStatus.SUCCEEDED)
    trace_context = _FakeTraceContext()
    use_case = HandleRunRequestedUseCase(execute_run, trace_context)
    message = _message()

    outcome = use_case(message)

    assert outcome.ack is True
    assert outcome.status == RunStatus.SUCCEEDED
    assert execute_run.calls == [message.run_id]


def test_lease_held_is_not_acked() -> None:
    execute_run = _FakeExecuteRun(error=LeaseHeld(uuid4()))
    trace_context = _FakeTraceContext()
    use_case = HandleRunRequestedUseCase(execute_run, trace_context)

    outcome = use_case(_message())

    assert outcome.ack is False
    assert outcome.status is None


def test_missing_declaration_is_acked_and_logs_a_warning(
    caplog: pytest.LogCaptureFixture,
) -> None:
    run_id = uuid4()
    execute_run = _FakeExecuteRun(error=RuntimeError(f"no run declaration found for run {run_id}"))
    trace_context = _FakeTraceContext()
    use_case = HandleRunRequestedUseCase(execute_run, trace_context)
    message = RequestedMessage(
        message_id="1-0", run_id=run_id, agent_version_id=uuid4(), traceparent=None
    )

    with caplog.at_level("WARNING"):
        outcome = use_case(message)

    assert outcome.ack is True
    assert outcome.status is None
    warnings = [r for r in caplog.records if r.levelname == "WARNING"]
    assert warnings, "no run declaration found 은 WARNING 으로 로그되어야 합니다"
    assert any(str(run_id) in r.message or str(run_id) in str(r.__dict__) for r in warnings)


def test_activates_trace_context_with_the_message_traceparent() -> None:
    execute_run = _FakeExecuteRun(result=RunStatus.SUCCEEDED)
    trace_context = _FakeTraceContext()
    use_case = HandleRunRequestedUseCase(execute_run, trace_context)
    message = _message(traceparent="00-abc-01")

    use_case(message)

    assert trace_context.activated == ["00-abc-01"]


def test_other_exceptions_propagate_and_are_not_swallowed() -> None:
    execute_run = _FakeExecuteRun(error=ValueError("boom"))
    trace_context = _FakeTraceContext()
    use_case = HandleRunRequestedUseCase(execute_run, trace_context)

    with pytest.raises(ValueError):
        use_case(_message())
