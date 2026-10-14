"""spec 0005 2.1, 2.9 개정 2 (P4-2a A): `HandleWorkflowRequestedUseCase` - ack 규칙.

`test_handle_run_requested.py` 와 같은 네 규칙을 Workflow 쪽에서 증명합니다: 정상은 ack,
`WorkflowLeaseHeld` 는 ack 하지 않음(다음 `XAUTOCLAIM` 이 다시 봄), 선언 없음(`RuntimeError`)은
독약이므로 WARNING + ack, 그 밖의 예외는 흡수하지 않고 올립니다. `traceparent` 는 그대로
`TraceContext.activate` 에 전달됩니다.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from uuid import UUID, uuid4

import pytest
from aether_worker.application.ports.inbound.handle_workflow_requested import (
    WorkflowRequestedMessage,
)
from aether_worker.application.usecases.handle_workflow_requested import (
    HandleWorkflowRequestedUseCase,
)
from aether_workflow.application.ports.inbound.advance_workflow_run import WorkflowLeaseHeld
from aether_workflow.domain.run_status import WorkflowRunStatus


class _FakeAdvanceWorkflowRun:
    def __init__(
        self, *, result: WorkflowRunStatus | None = None, error: Exception | None = None
    ) -> None:
        self._result = result
        self._error = error
        self.calls: list[UUID] = []

    def __call__(self, workflow_run_id: UUID) -> WorkflowRunStatus:
        self.calls.append(workflow_run_id)
        if self._error is not None:
            raise self._error
        assert self._result is not None
        return self._result


class _FakeWorkflowTraceContext:
    def __init__(self) -> None:
        self.activated: list[str | None] = []

    @contextmanager
    def activate(self, traceparent: str | None) -> Iterator[None]:
        self.activated.append(traceparent)
        yield


def _message(traceparent: str | None = "00-trace-01") -> WorkflowRequestedMessage:
    return WorkflowRequestedMessage(
        message_id="1-0",
        workflow_run_id=uuid4(),
        workflow_version_id=uuid4(),
        traceparent=traceparent,
    )


def test_successful_advance_is_acked_with_its_status() -> None:
    advance = _FakeAdvanceWorkflowRun(result=WorkflowRunStatus.SUCCEEDED)
    use_case = HandleWorkflowRequestedUseCase(advance, _FakeWorkflowTraceContext())
    message = _message()

    outcome = use_case(message)

    assert outcome.ack is True
    assert outcome.status is WorkflowRunStatus.SUCCEEDED
    assert advance.calls == [message.workflow_run_id]


def test_lease_held_is_not_acked() -> None:
    advance = _FakeAdvanceWorkflowRun(error=WorkflowLeaseHeld(uuid4()))
    use_case = HandleWorkflowRequestedUseCase(advance, _FakeWorkflowTraceContext())

    outcome = use_case(_message())

    assert outcome.ack is False
    assert outcome.status is None


def test_missing_declaration_is_acked_and_logs_a_warning(
    caplog: pytest.LogCaptureFixture,
) -> None:
    advance = _FakeAdvanceWorkflowRun(error=RuntimeError("no declaration"))
    use_case = HandleWorkflowRequestedUseCase(advance, _FakeWorkflowTraceContext())
    message = _message()

    with caplog.at_level("WARNING"):
        outcome = use_case(message)

    assert outcome.ack is True
    assert outcome.status is None
    assert any(
        record.levelname == "WARNING"
        and getattr(record, "workflow_run_id", None) == str(message.workflow_run_id)
        for record in caplog.records
    )


def test_unexpected_errors_are_not_swallowed() -> None:
    advance = _FakeAdvanceWorkflowRun(error=ConnectionError("db down"))
    use_case = HandleWorkflowRequestedUseCase(advance, _FakeWorkflowTraceContext())

    with pytest.raises(ConnectionError):
        use_case(_message())


def test_traceparent_is_activated_around_the_advance() -> None:
    advance = _FakeAdvanceWorkflowRun(result=WorkflowRunStatus.SUCCEEDED)
    trace_context = _FakeWorkflowTraceContext()
    use_case = HandleWorkflowRequestedUseCase(advance, trace_context)

    use_case(_message("00-abc-01"))
    use_case(_message(None))

    assert trace_context.activated == ["00-abc-01", None]
