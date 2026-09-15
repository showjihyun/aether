"""spec 0002 2.8, R-4, R-11, R-15 (P1-7): 재시도·백오프·타임아웃 정책.

`FakeClock` 이 결정적 시계·`sleep` 기록을 제공합니다(R-11) — 실제 대기는 0 이고,
`clock.sleep_calls` 로 정확한 백오프 지연 값을 단언합니다. 타임아웃 기준은
`Clock.now()` 와 저장된 `RunState.started_at` 입니다(spec 0002 2.8 [편집], monotonic
은 재개를 넘어 보존되지 않으므로 — 이 unit 의 설계 결정 1).

기존 `test_execute_run.py`·`test_resume.py`·`test_observation_boundary.py` 는
이 unit 이 손대지 않은 계약(재시도 0 인 기본 정의)이라 수정 없이 통과해야 합니다.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import UUID, uuid4

from aether_runtime.adapters.outbound.model_gateway.fake import FakeModelGateway
from aether_runtime.adapters.outbound.tools.registry import InMemoryToolRegistry
from aether_runtime.application.ports.outbound.model_gateway import (
    ModelError,
    ModelGateway,
    ModelRequest,
    ModelResponse,
)
from aether_runtime.application.ports.outbound.run_declaration_reader import RunDeclaration
from aether_runtime.application.usecases.execute_run import ExecuteRunUseCase
from aether_runtime.domain.failure import FailureReason
from aether_runtime.domain.run import RunState, RunStatus
from aether_runtime.domain.tools import ToolCall, ToolResult

from packages.runtime.tests.fakes import (
    FakeClock,
    FakeEventSink,
    FakeRunDeclarationReader,
    FakeRunStateStore,
    FakeStatusNotifier,
    FakeTool,
    FakeToolRegistry,
    InMemoryTracer,
)

_OWNER = "worker-test"


def _definition(
    *,
    tools: list[str] | None = None,
    max_steps: int = 8,
    timeout_seconds: int = 120,
    model_retries: int = 0,
    tool_retries: int = 0,
    backoff: dict[str, float] | None = None,
) -> dict[str, Any]:
    policy: dict[str, Any] = {
        "timeout_seconds": timeout_seconds,
        "max_steps": max_steps,
        "model_retries": model_retries,
        "tool_retries": tool_retries,
    }
    if backoff is not None:
        policy["backoff"] = backoff
    return {
        "schema_version": 1,
        "system_prompt": "You are a helpful test agent.",
        "model": {"id": "test-model"},
        "tools": tools or [],
        "policy": policy,
    }


def _declare(definition: dict[str, Any]) -> tuple[UUID, FakeRunDeclarationReader]:
    run_id = uuid4()
    agent_version_id = uuid4()
    reader = FakeRunDeclarationReader(
        {run_id: RunDeclaration(run_id=run_id, agent_version_id=agent_version_id, input="hi")},
        {agent_version_id: definition},
    )
    return run_id, reader


def _usecase(
    *,
    run_id: UUID,
    reader: FakeRunDeclarationReader,
    gateway: ModelGateway,
    clock: FakeClock,
    store: FakeRunStateStore,
    events: FakeEventSink,
    notifier: FakeStatusNotifier,
    tools: Any = None,
) -> ExecuteRunUseCase:
    return ExecuteRunUseCase(
        store,
        reader,
        gateway,
        tools if tools is not None else InMemoryToolRegistry(clock),
        events,
        notifier,
        InMemoryTracer(),
        clock,
        owner=_OWNER,
    )


def _last_status_payload(events: FakeEventSink) -> dict[str, Any]:
    status_events = [e for e in events.published if e.type == "run.status"]
    return status_events[-1].payload


class _SingleToolRegistry:
    """`ToolRegistry` 포트 최소 구현 — 도구 하나만 압니다(test_run_end_to_end.py 와
    같은 패턴)."""

    def __init__(self, tool: Any) -> None:
        self._tool = tool

    def get(self, name: str) -> Any:
        if name != self._tool.name:
            raise KeyError(name)
        return self._tool

    def names(self) -> frozenset[str]:
        return frozenset({self._tool.name})


@dataclass
class _FlakyTool:
    """`fail_times` 번 예외를 던진 뒤부터는 성공합니다(spec 0002 2.8 도구 재시도)."""

    name: str = "calculator"
    description: str = "flaky calculator"
    input_schema: dict[str, Any] = field(default_factory=dict)
    fail_times: int = 1
    calls: int = 0

    def run(self, arguments: dict[str, Any]) -> ToolResult:
        self.calls += 1
        if self.calls <= self.fail_times:
            raise RuntimeError("boom")
        return ToolResult(content="4")


@dataclass
class _AlwaysFailingTool:
    name: str = "calculator"
    description: str = "always fails"
    input_schema: dict[str, Any] = field(default_factory=dict)
    calls: int = 0

    def run(self, arguments: dict[str, Any]) -> ToolResult:
        self.calls += 1
        raise RuntimeError("boom")


@dataclass
class _ClockAdvancingTool:
    """`run()` 마다 `clock` 을 `advance_by` 초만큼 전진시킵니다 — 도구 실행 자체가
    Run 예산을 소모하는 시나리오(항목 9·10)를 재현합니다."""

    clock: FakeClock
    advance_by: float
    name: str = "calculator"
    description: str = "advances the clock"
    input_schema: dict[str, Any] = field(default_factory=dict)
    calls: int = 0

    def run(self, arguments: dict[str, Any]) -> ToolResult:
        self.calls += 1
        self.clock.advance(self.advance_by)
        return ToolResult(content="ok")


@dataclass
class _TimeoutThenClockAdvanceGateway:
    """`complete()` 가 항상 `ModelError(kind="timeout")` 을 내면서, 그 호출 자체가
    `advance_by` 초를 소모했다고 시계를 전진시킵니다(항목 12: 실제 호출이 타임아웃
    상한만큼 블록했다고 가정)."""

    clock: FakeClock
    advance_by: float
    calls: list[ModelRequest] = field(default_factory=list)

    def complete(self, request: ModelRequest) -> ModelResponse:
        self.calls.append(request)
        self.clock.advance(self.advance_by)
        raise ModelError(kind="timeout")

    def stream(self, request: ModelRequest) -> Any:
        raise NotImplementedError

    def embed(self, texts: list[str]) -> list[list[float]]:
        raise NotImplementedError


def test_model_5xx_retried_twice_then_succeeds() -> None:
    """spec 0002 2.8: 5xx 2회 뒤 성공 -- `model_retries=2` 로 통과, 백오프는 기본값
    (`base=0.5`)의 지수 열 `[0.5, 1.0]`."""
    definition = _definition(model_retries=2)
    run_id, reader = _declare(definition)
    clock = FakeClock()
    store = FakeRunStateStore(clock)
    events = FakeEventSink()
    notifier = FakeStatusNotifier()
    gateway = FakeModelGateway(
        [
            ModelError(kind="http", status=500),
            ModelError(kind="http", status=500),
            ModelResponse(text="ok", finish_reason="stop"),
        ]
    )
    usecase = _usecase(
        run_id=run_id,
        reader=reader,
        gateway=gateway,
        clock=clock,
        store=store,
        events=events,
        notifier=notifier,
    )

    status = usecase(run_id)

    assert status == RunStatus.SUCCEEDED
    assert clock.sleep_calls == [0.5, 1.0]
    assert len(gateway.calls) == 3


def test_model_5xx_exhausts_retries_and_fails_with_reason() -> None:
    """spec 0002 2.8: 5xx 가 `model_retries + 1` 회 -- `failed(model_error)`, 백오프
    `[0.5, 1.0]`(마지막 실패 뒤에는 재시도가 없으므로 세 번째 지연은 없습니다)."""
    definition = _definition(model_retries=2)
    run_id, reader = _declare(definition)
    clock = FakeClock()
    store = FakeRunStateStore(clock)
    events = FakeEventSink()
    notifier = FakeStatusNotifier()
    gateway = FakeModelGateway([ModelError(kind="http", status=500)] * 3)
    usecase = _usecase(
        run_id=run_id,
        reader=reader,
        gateway=gateway,
        clock=clock,
        store=store,
        events=events,
        notifier=notifier,
    )

    status = usecase(run_id)

    assert status == RunStatus.FAILED
    assert _last_status_payload(events)["failure_reason"] == FailureReason.MODEL_ERROR.value
    assert clock.sleep_calls == [0.5, 1.0]
    assert len(gateway.calls) == 3


def test_model_4xx_fails_immediately_without_retry() -> None:
    """spec 0002 2.8: `http` 4xx(429 제외)는 재시도 없이 즉시 `failed(model_error)`."""
    definition = _definition(model_retries=2)
    run_id, reader = _declare(definition)
    clock = FakeClock()
    store = FakeRunStateStore(clock)
    events = FakeEventSink()
    notifier = FakeStatusNotifier()
    gateway = FakeModelGateway([ModelError(kind="http", status=400)])
    usecase = _usecase(
        run_id=run_id,
        reader=reader,
        gateway=gateway,
        clock=clock,
        store=store,
        events=events,
        notifier=notifier,
    )

    status = usecase(run_id)

    assert status == RunStatus.FAILED
    assert _last_status_payload(events)["failure_reason"] == FailureReason.MODEL_ERROR.value
    assert clock.sleep_calls == []
    assert len(gateway.calls) == 1


def test_model_429_is_retried() -> None:
    """spec 0002 2.8: `429` 는 5xx 와 같이 재시도 대상입니다."""
    definition = _definition(model_retries=1)
    run_id, reader = _declare(definition)
    clock = FakeClock()
    store = FakeRunStateStore(clock)
    events = FakeEventSink()
    notifier = FakeStatusNotifier()
    gateway = FakeModelGateway(
        [ModelError(kind="http", status=429), ModelResponse(text="ok", finish_reason="stop")]
    )
    usecase = _usecase(
        run_id=run_id,
        reader=reader,
        gateway=gateway,
        clock=clock,
        store=store,
        events=events,
        notifier=notifier,
    )

    status = usecase(run_id)

    assert status == RunStatus.SUCCEEDED
    assert clock.sleep_calls == [0.5]
    assert len(gateway.calls) == 2


def test_backoff_delay_is_capped_at_max_seconds() -> None:
    """spec 0002 2.3, 2.8: `base=4, max=5` 에서 둘째 지연은 상한 5 에서 멈춥니다
    (`min(4*2, 5) == 5`)."""
    definition = _definition(model_retries=2, backoff={"base_seconds": 4.0, "max_seconds": 5.0})
    run_id, reader = _declare(definition)
    clock = FakeClock()
    store = FakeRunStateStore(clock)
    events = FakeEventSink()
    notifier = FakeStatusNotifier()
    gateway = FakeModelGateway(
        [
            ModelError(kind="http", status=500),
            ModelError(kind="http", status=500),
            ModelResponse(text="ok", finish_reason="stop"),
        ]
    )
    usecase = _usecase(
        run_id=run_id,
        reader=reader,
        gateway=gateway,
        clock=clock,
        store=store,
        events=events,
        notifier=notifier,
    )

    status = usecase(run_id)

    assert status == RunStatus.SUCCEEDED
    assert clock.sleep_calls == [4.0, 5.0]


def test_tool_exception_retried_once_then_succeeds() -> None:
    """spec 0002 2.8: 도구 예외 -- `tool_retries=1` 에서 1회 실패 뒤 성공하면
    `succeeded`."""
    definition = _definition(tools=["calculator"], tool_retries=1)
    run_id, reader = _declare(definition)
    clock = FakeClock()
    store = FakeRunStateStore(clock)
    events = FakeEventSink()
    notifier = FakeStatusNotifier()
    tool = _FlakyTool(fail_times=1)
    gateway = FakeModelGateway(
        [
            ModelResponse(
                tool_calls=[ToolCall(id="call_1", name="calculator", arguments={})],
                finish_reason="tool_calls",
            ),
            ModelResponse(text="4 입니다.", finish_reason="stop"),
        ]
    )
    usecase = _usecase(
        run_id=run_id,
        reader=reader,
        gateway=gateway,
        clock=clock,
        store=store,
        events=events,
        notifier=notifier,
        tools=_SingleToolRegistry(tool),
    )

    status = usecase(run_id)

    assert status == RunStatus.SUCCEEDED
    assert tool.calls == 2
    assert clock.sleep_calls == [0.5]


def test_tool_exception_exhausts_retries_and_fails_with_reason() -> None:
    """spec 0002 2.8: 도구 예외 소진 -- `failed(tool_error)`."""
    definition = _definition(tools=["calculator"], tool_retries=1)
    run_id, reader = _declare(definition)
    clock = FakeClock()
    store = FakeRunStateStore(clock)
    events = FakeEventSink()
    notifier = FakeStatusNotifier()
    tool = _AlwaysFailingTool()
    gateway = FakeModelGateway(
        [
            ModelResponse(
                tool_calls=[ToolCall(id="call_1", name="calculator", arguments={})],
                finish_reason="tool_calls",
            )
        ]
    )
    usecase = _usecase(
        run_id=run_id,
        reader=reader,
        gateway=gateway,
        clock=clock,
        store=store,
        events=events,
        notifier=notifier,
        tools=_SingleToolRegistry(tool),
    )

    status = usecase(run_id)

    assert status == RunStatus.FAILED
    assert _last_status_payload(events)["failure_reason"] == FailureReason.TOOL_ERROR.value
    assert tool.calls == 2
    assert clock.sleep_calls == [0.5]


def test_tool_result_is_error_is_not_retried_and_reaches_the_model_as_observation() -> None:
    """spec 0002 2.8: `ToolResult(is_error=True)` 는 예외가 아니므로 재시도 대상이
    아니고, 정상적인 `Observation` 으로 모델에 돌아갑니다."""
    definition = _definition(tools=["calculator"])
    run_id, reader = _declare(definition)
    clock = FakeClock()
    store = FakeRunStateStore(clock)
    events = FakeEventSink()
    notifier = FakeStatusNotifier()
    tool = FakeTool(name="calculator", result=ToolResult(content="bad expr", is_error=True))
    registry = FakeToolRegistry({"calculator": tool})
    gateway = FakeModelGateway(
        [
            ModelResponse(
                tool_calls=[ToolCall(id="call_1", name="calculator", arguments={})],
                finish_reason="tool_calls",
            ),
            ModelResponse(text="다시 시도하세요.", finish_reason="stop"),
        ]
    )
    usecase = _usecase(
        run_id=run_id,
        reader=reader,
        gateway=gateway,
        clock=clock,
        store=store,
        events=events,
        notifier=notifier,
        tools=registry,
    )

    status = usecase(run_id)

    assert status == RunStatus.SUCCEEDED
    assert len(tool.calls) == 1
    assert clock.sleep_calls == []
    tool_result_events = [e for e in events.published if e.type == "tool.result"]
    assert tool_result_events[0].payload["is_error"] is True
    second_request = gateway.calls[1]
    tool_message = next(m for m in second_request.messages if m.role == "tool")
    assert "bad expr" in tool_message.content


def test_tool_advancing_clock_past_deadline_times_out_at_next_step_start() -> None:
    """spec 0002 2.8: 도구 실행이 예산을 다 써버리면(시계 전진), 다음 단계 시작에서
    `timed_out` -- `failure_reason` 없음."""
    clock = FakeClock()
    tool = _ClockAdvancingTool(clock=clock, advance_by=61.0)
    definition = _definition(tools=["calculator"], timeout_seconds=60)
    run_id, reader = _declare(definition)
    store = FakeRunStateStore(clock)
    events = FakeEventSink()
    notifier = FakeStatusNotifier()
    gateway = FakeModelGateway(
        [
            ModelResponse(
                tool_calls=[ToolCall(id="call_1", name="calculator", arguments={})],
                finish_reason="tool_calls",
            ),
            ModelResponse(text="never reached", finish_reason="stop"),
        ]
    )
    usecase = _usecase(
        run_id=run_id,
        reader=reader,
        gateway=gateway,
        clock=clock,
        store=store,
        events=events,
        notifier=notifier,
        tools=_SingleToolRegistry(tool),
    )

    status = usecase(run_id)

    assert status == RunStatus.TIMED_OUT
    assert "failure_reason" not in _last_status_payload(events)
    statuses = [e.payload["status"] for e in events.published if e.type == "run.status"]
    assert statuses[-1] == RunStatus.TIMED_OUT.value
    assert len(gateway.calls) == 1


def test_model_call_receives_remaining_budget_as_timeout_seconds() -> None:
    """spec 0002 2.8: 모델 호출에 넘긴 `timeout_seconds` 가 잔여 시간입니다 -- 도구가
    시계를 30초 전진시킨 뒤의 두 번째 호출은 `120 - 30 == 90`."""
    clock = FakeClock()
    tool = _ClockAdvancingTool(clock=clock, advance_by=30.0)
    definition = _definition(tools=["calculator"], timeout_seconds=120)
    run_id, reader = _declare(definition)
    store = FakeRunStateStore(clock)
    events = FakeEventSink()
    notifier = FakeStatusNotifier()
    gateway = FakeModelGateway(
        [
            ModelResponse(
                tool_calls=[ToolCall(id="call_1", name="calculator", arguments={})],
                finish_reason="tool_calls",
            ),
            ModelResponse(text="done", finish_reason="stop"),
        ]
    )
    usecase = _usecase(
        run_id=run_id,
        reader=reader,
        gateway=gateway,
        clock=clock,
        store=store,
        events=events,
        notifier=notifier,
        tools=_SingleToolRegistry(tool),
    )

    status = usecase(run_id)

    assert status == RunStatus.SUCCEEDED
    assert gateway.calls[0].timeout_seconds == 120
    assert gateway.calls[1].timeout_seconds == 90


def test_remaining_budget_smaller_than_backoff_delay_times_out_without_sleeping() -> None:
    """spec 0002 2.8: 잔여가 백오프 지연보다 작으면 기다리지 않고 `timed_out`."""
    definition = _definition(
        timeout_seconds=1, model_retries=1, backoff={"base_seconds": 2.0, "max_seconds": 8.0}
    )
    run_id, reader = _declare(definition)
    clock = FakeClock()
    store = FakeRunStateStore(clock)
    events = FakeEventSink()
    notifier = FakeStatusNotifier()
    gateway = FakeModelGateway(
        [ModelError(kind="http", status=500), ModelResponse(text="unreached", finish_reason="stop")]
    )
    usecase = _usecase(
        run_id=run_id,
        reader=reader,
        gateway=gateway,
        clock=clock,
        store=store,
        events=events,
        notifier=notifier,
    )

    status = usecase(run_id)

    assert status == RunStatus.TIMED_OUT
    assert "failure_reason" not in _last_status_payload(events)
    assert clock.sleep_calls == []
    assert len(gateway.calls) == 1


def test_model_timeout_error_with_no_remaining_budget_is_not_retried() -> None:
    """spec 0002 2.8: `ModelError(kind="timeout")` 이면서 그 시점 잔여가 이미 0 이하면
    재시도하지 않고 즉시 `timed_out`."""
    clock = FakeClock()
    gateway = _TimeoutThenClockAdvanceGateway(clock=clock, advance_by=11.0)
    definition = _definition(timeout_seconds=10, model_retries=2)
    run_id, reader = _declare(definition)
    store = FakeRunStateStore(clock)
    events = FakeEventSink()
    notifier = FakeStatusNotifier()
    usecase = _usecase(
        run_id=run_id,
        reader=reader,
        gateway=gateway,
        clock=clock,
        store=store,
        events=events,
        notifier=notifier,
    )

    status = usecase(run_id)

    assert status == RunStatus.TIMED_OUT
    assert "failure_reason" not in _last_status_payload(events)
    assert clock.sleep_calls == []
    assert len(gateway.calls) == 1


def test_resumed_run_over_budget_times_out_at_first_step_without_calling_the_model() -> None:
    """spec 0002 2.8, R-15, R-16: 재개 뒤에도 예산은 유지됩니다 -- 저장된
    `started_at` 기준으로 이미 초과했다면 첫 단계 시작에서 모델을 부르지 않고
    `timed_out`."""
    definition = _definition(timeout_seconds=120)
    run_id, reader = _declare(definition)
    clock = FakeClock()
    store = FakeRunStateStore(clock)
    started_at = clock.now()
    store.set_status(run_id, RunStatus.RUNNING, started_at=started_at)
    prior_state = RunState(
        run_id=run_id,
        status=RunStatus.RUNNING,
        step=1,
        last_seq=3,
        started_at=started_at,
        messages=[],
    )
    store.save(prior_state)
    clock.advance(200)  # 120초 예산을 이미 넘긴 뒤 재개합니다.

    events = FakeEventSink()
    notifier = FakeStatusNotifier()
    gateway = FakeModelGateway([ModelResponse(text="unreached", finish_reason="stop")])
    usecase = _usecase(
        run_id=run_id,
        reader=reader,
        gateway=gateway,
        clock=clock,
        store=store,
        events=events,
        notifier=notifier,
    )

    status = usecase(run_id)

    assert status == RunStatus.TIMED_OUT
    assert gateway.calls == []
    assert "failure_reason" not in _last_status_payload(events)


def test_definition_invalid_still_fails_without_retry_policy_involvement() -> None:
    """spec 0002 2.8: 정책 도입 뒤에도 `definition_invalid` 는 재시도와 무관하게
    그대로 동작합니다(회귀 방지)."""
    run_id, reader = _declare({"schema_version": 999})
    clock = FakeClock()
    store = FakeRunStateStore(clock)
    events = FakeEventSink()
    notifier = FakeStatusNotifier()
    gateway = FakeModelGateway([])
    usecase = _usecase(
        run_id=run_id,
        reader=reader,
        gateway=gateway,
        clock=clock,
        store=store,
        events=events,
        notifier=notifier,
    )

    status = usecase(run_id)

    assert status == RunStatus.FAILED
    assert _last_status_payload(events)["failure_reason"] == FailureReason.DEFINITION_INVALID.value
    assert gateway.calls == []
    assert clock.sleep_calls == []
