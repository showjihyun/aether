"""spec 0002 2.4, 2.6, 2.7, 2.8, D-10, D-11, R-15: `ExecuteRunUseCase` — Planner/Executor
루프. fake 어댑터로 도구를 부르는/부르지 않는 시나리오가 결정적으로 통과하고, 실패
사유(`max_steps_exceeded`·`unknown_tool`·`definition_invalid`·`model_error`)·취소·
전이 순서·`seq` 연속성·`StatusMessage` 정합·`run.finished` 위치·`started_at`/
`finished_at`·종결 시 lease `release` 를 증명합니다.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

from aether_runtime.adapters.outbound.model_gateway.fake import FakeModelGateway
from aether_runtime.adapters.outbound.tools.registry import InMemoryToolRegistry
from aether_runtime.application.ports.outbound.model_gateway import ModelError, ModelResponse
from aether_runtime.application.ports.outbound.run_declaration_reader import RunDeclaration
from aether_runtime.application.ports.outbound.tools import ToolRegistry
from aether_runtime.application.usecases.execute_run import ExecuteRunUseCase
from aether_runtime.domain.failure import FailureReason
from aether_runtime.domain.run import RunStatus
from aether_runtime.domain.tools import ToolCall

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


def _definition(tools: list[str] | None = None, max_steps: int = 8) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "system_prompt": "You are a helpful test agent.",
        "model": {"id": "test-model"},
        "tools": tools or [],
        "policy": {
            "timeout_seconds": 120,
            "max_steps": max_steps,
            "model_retries": 0,
            "tool_retries": 0,
        },
    }


def _declare(
    declarations: dict[UUID, RunDeclaration],
    definitions: dict[UUID, dict[str, Any]],
    *,
    definition: dict[str, Any] | None = None,
    run_input: str = "do the thing",
) -> tuple[UUID, UUID]:
    run_id = uuid4()
    agent_version_id = uuid4()
    declarations[run_id] = RunDeclaration(
        run_id=run_id, agent_version_id=agent_version_id, input=run_input
    )
    definitions[agent_version_id] = definition if definition is not None else _definition()
    return run_id, agent_version_id


def _harness(
    *, definition: dict[str, Any] | None = None
) -> tuple[
    FakeClock,
    FakeRunStateStore,
    FakeRunDeclarationReader,
    FakeEventSink,
    FakeStatusNotifier,
    InMemoryTracer,
    UUID,
    UUID,
]:
    clock = FakeClock()
    store = FakeRunStateStore(clock)
    declarations: dict[UUID, RunDeclaration] = {}
    definitions: dict[UUID, dict[str, Any]] = {}
    run_id, agent_version_id = _declare(declarations, definitions, definition=definition)
    reader = FakeRunDeclarationReader(declarations, definitions)
    events = FakeEventSink()
    notifier = FakeStatusNotifier()
    tracer = InMemoryTracer()
    return clock, store, reader, events, notifier, tracer, run_id, agent_version_id


def _usecase(
    *,
    gateway: FakeModelGateway,
    store: FakeRunStateStore,
    reader: FakeRunDeclarationReader,
    events: FakeEventSink,
    notifier: FakeStatusNotifier,
    tracer: InMemoryTracer,
    clock: FakeClock,
    tools: ToolRegistry | None = None,
) -> ExecuteRunUseCase:
    return ExecuteRunUseCase(
        store=store,
        declarations=reader,
        gateway=gateway,
        tools=tools if tools is not None else InMemoryToolRegistry(clock),
        events=events,
        notifier=notifier,
        tracer=tracer,
        clock=clock,
        owner=_OWNER,
    )


def test_scenario_without_tool_call_succeeds() -> None:
    """spec 0002 2.6: 도구를 부르지 않는 시나리오 — 모델이 바로 최종 응답."""
    clock, store, reader, events, notifier, tracer, run_id, _ = _harness()
    gateway = FakeModelGateway([ModelResponse(text="4 입니다.", finish_reason="stop")])
    usecase = _usecase(
        gateway=gateway,
        store=store,
        reader=reader,
        events=events,
        notifier=notifier,
        tracer=tracer,
        clock=clock,
    )

    status = usecase(run_id)

    assert status == RunStatus.SUCCEEDED
    assert store.status(run_id) == RunStatus.SUCCEEDED


def test_scenario_with_tool_call_succeeds_and_observation_is_a_tool_message() -> None:
    """spec 0002 2.6, R-14: 도구를 부르는 시나리오. 두 번째 모델 요청의 메시지에
    `role="tool"` + `tool_call_id` 로 관측 결과가 실립니다."""
    clock, store, reader, events, notifier, tracer, run_id, _ = _harness(
        definition=_definition(tools=["calculator"])
    )
    gateway = FakeModelGateway(
        [
            ModelResponse(
                tool_calls=[
                    ToolCall(id="call_1", name="calculator", arguments={"expression": "2+2"})
                ],
                finish_reason="tool_calls",
            ),
            ModelResponse(text="4 입니다.", finish_reason="stop"),
        ]
    )
    usecase = _usecase(
        gateway=gateway,
        store=store,
        reader=reader,
        events=events,
        notifier=notifier,
        tracer=tracer,
        clock=clock,
    )

    status = usecase(run_id)

    assert status == RunStatus.SUCCEEDED
    second_request = gateway.calls[1]
    tool_messages = [m for m in second_request.messages if m.role == "tool"]
    assert len(tool_messages) == 1
    assert tool_messages[0].tool_call_id == "call_1"
    assert "4" in tool_messages[0].content


def test_max_steps_exceeded_fails_with_reason() -> None:
    """spec 0002 2.3, 2.8: `policy.max_steps` 초과 → `failed(max_steps_exceeded)`."""
    clock, store, reader, events, notifier, tracer, run_id, _ = _harness(
        definition=_definition(tools=["calculator"], max_steps=1)
    )
    gateway = FakeModelGateway(
        [
            ModelResponse(
                tool_calls=[
                    ToolCall(id="call_1", name="calculator", arguments={"expression": "1+1"})
                ],
                finish_reason="tool_calls",
            ),
            ModelResponse(
                tool_calls=[
                    ToolCall(id="call_2", name="calculator", arguments={"expression": "1+1"})
                ],
                finish_reason="tool_calls",
            ),
        ]
    )
    usecase = _usecase(
        gateway=gateway,
        store=store,
        reader=reader,
        events=events,
        notifier=notifier,
        tracer=tracer,
        clock=clock,
    )

    status = usecase(run_id)

    assert status == RunStatus.FAILED
    assert store.status(run_id) == RunStatus.FAILED


def test_unknown_tool_call_fails_with_reason() -> None:
    """spec 0002 2.8: 정의가 레지스트리에 없는 도구를 요구 → `failed(unknown_tool)` —
    api 의 `AgentDefinition` 검증을 지나쳤다는 전제로, worker 가 런타임에 막습니다."""
    clock, store, reader, events, notifier, tracer, run_id, _ = _harness()
    gateway = FakeModelGateway(
        [
            ModelResponse(
                tool_calls=[ToolCall(id="call_1", name="search", arguments={})],
                finish_reason="tool_calls",
            )
        ]
    )
    usecase = _usecase(
        gateway=gateway,
        store=store,
        reader=reader,
        events=events,
        notifier=notifier,
        tracer=tracer,
        clock=clock,
    )

    status = usecase(run_id)

    assert status == RunStatus.FAILED
    final_status_events = [e for e in events.published if e.type == "run.status"]
    assert final_status_events[-1].payload["failure_reason"] == FailureReason.UNKNOWN_TOOL.value


def test_tool_call_outside_definition_tools_fails_and_is_not_executed() -> None:
    """리뷰 C, spec 0002 2.6·2.8: 허용 집합은 **`definition.tools`** 입니다 — 레지스트리에
    등록되어 있어도 정의가 허용하지 않은 도구를 모델이 부르면 `unknown_tool` 이고,
    그 도구는 실행되지 않습니다."""
    clock, store, reader, events, notifier, tracer, run_id, _ = _harness(
        definition=_definition(tools=["clock"])
    )
    gateway = FakeModelGateway(
        [
            ModelResponse(
                tool_calls=[
                    ToolCall(id="call_1", name="calculator", arguments={"expression": "1+1"})
                ],
                finish_reason="tool_calls",
            )
        ]
    )
    calculator = FakeTool(name="calculator")
    registry = FakeToolRegistry({"clock": FakeTool(name="clock"), "calculator": calculator})
    usecase = _usecase(
        gateway=gateway,
        store=store,
        reader=reader,
        events=events,
        notifier=notifier,
        tracer=tracer,
        clock=clock,
        tools=registry,
    )

    status = usecase(run_id)

    assert status == RunStatus.FAILED
    assert calculator.calls == []
    final_status_events = [e for e in events.published if e.type == "run.status"]
    assert final_status_events[-1].payload["failure_reason"] == FailureReason.UNKNOWN_TOOL.value


def test_definition_invalid_fails_with_reason() -> None:
    """spec 0002 2.8: `AgentDefinition.model_validate` 실패 → `failed(definition_invalid)`.

    `queued -> running -> failed` 순서를 반드시 거칩니다(2.4 전이표에 `queued ->
    failed` 직접 전이가 없으므로)."""
    clock, store, reader, events, notifier, tracer, run_id, _ = _harness(
        definition={"schema_version": 999}
    )
    gateway = FakeModelGateway([])
    usecase = _usecase(
        gateway=gateway,
        store=store,
        reader=reader,
        events=events,
        notifier=notifier,
        tracer=tracer,
        clock=clock,
    )

    status = usecase(run_id)

    assert status == RunStatus.FAILED
    statuses = [e.payload["status"] for e in events.published if e.type == "run.status"]
    assert statuses == [RunStatus.RUNNING.value, RunStatus.FAILED.value]
    assert gateway.calls == []


def test_model_error_fails_immediately_without_retry() -> None:
    """spec 0002 2.8 (P1-4 순서 1): 이 단위는 재시도 없이 즉시 `failed(model_error)`
    — 재시도 정책은 P1-7."""
    clock, store, reader, events, notifier, tracer, run_id, _ = _harness()
    gateway = FakeModelGateway([ModelError(kind="http", status=500)])
    usecase = _usecase(
        gateway=gateway,
        store=store,
        reader=reader,
        events=events,
        notifier=notifier,
        tracer=tracer,
        clock=clock,
    )

    status = usecase(run_id)

    assert status == RunStatus.FAILED
    assert len(gateway.calls) == 1


def test_cancel_observed_between_steps_yields_cancelled() -> None:
    """spec 0002 2.4, D-11, R-14: 취소의 정본은 `cancel_requested_at` 하나 — 첫 번째
    단계(도구 호출)가 끝난 뒤, 다음 단계 시작에서 취소를 관측해 `cancelled` 로
    끝납니다. fake 모델 응답은 "tool_call 1회 뒤 최종" 이어야 다음 반복이 있습니다."""
    clock, store, reader, events, notifier, tracer, run_id, _ = _harness(
        definition=_definition(tools=["calculator"])
    )
    gateway = FakeModelGateway(
        [
            ModelResponse(
                tool_calls=[
                    ToolCall(id="call_1", name="calculator", arguments={"expression": "1+1"})
                ],
                finish_reason="tool_calls",
            ),
            ModelResponse(text="이 응답은 오지 않아야 합니다.", finish_reason="stop"),
        ]
    )

    class _CancelAfterFirstStepTools:
        """첫 도구 호출이 끝나는 시점에 취소를 관측시키는 계산기 래퍼."""

        name = "calculator"
        description = "wrapped calculator"
        input_schema: dict[str, Any] = {}

        def __init__(
            self, inner: Any, reader: FakeRunDeclarationReader, run_id: UUID, clock: FakeClock
        ) -> None:
            self._inner = inner
            self._reader = reader
            self._run_id = run_id
            self._clock = clock

        def run(self, arguments: dict[str, Any]) -> Any:
            result = self._inner.run(arguments)
            self._reader.set_cancel_requested(self._run_id, self._clock.now())
            return result

    class _Registry:
        def __init__(self, tool: Any) -> None:
            self._tool = tool

        def get(self, name: str) -> Any:
            if name != "calculator":
                raise KeyError(name)
            return self._tool

        def names(self) -> frozenset[str]:
            return frozenset({"calculator"})

    base_registry = InMemoryToolRegistry(clock)
    wrapped = _CancelAfterFirstStepTools(base_registry.get("calculator"), reader, run_id, clock)
    usecase = _usecase(
        gateway=gateway,
        store=store,
        reader=reader,
        events=events,
        notifier=notifier,
        tracer=tracer,
        clock=clock,
        tools=_Registry(wrapped),
    )

    status = usecase(run_id)

    assert status == RunStatus.CANCELLED
    assert len(gateway.calls) == 1


def test_transition_order_matches_published_run_status_events() -> None:
    """spec 0002 2.4, 2.7, R-3: `run.status` 이벤트 순서가 실제 전이 순서와 같습니다."""
    clock, store, reader, events, notifier, tracer, run_id, _ = _harness(
        definition=_definition(tools=["calculator"])
    )
    gateway = FakeModelGateway(
        [
            ModelResponse(
                tool_calls=[
                    ToolCall(id="call_1", name="calculator", arguments={"expression": "1+1"})
                ],
                finish_reason="tool_calls",
            ),
            ModelResponse(text="2 입니다.", finish_reason="stop"),
        ]
    )
    usecase = _usecase(
        gateway=gateway,
        store=store,
        reader=reader,
        events=events,
        notifier=notifier,
        tracer=tracer,
        clock=clock,
    )

    usecase(run_id)

    statuses = [e.payload["status"] for e in events.published if e.type == "run.status"]
    assert statuses == [
        RunStatus.RUNNING.value,
        RunStatus.WAITING.value,
        RunStatus.RUNNING.value,
        RunStatus.SUCCEEDED.value,
    ]


def test_seq_is_contiguous_from_one_and_run_finished_is_last() -> None:
    """spec 0002 2.7: `seq` 는 1 부터 단조 증가하고 `run.finished` 가 항상 마지막.
    봉투의 `v` 는 전부 `1`(D-4) — `model.delta`(예약, Phase 1 미발생)를 뺀 8종 중
    이 unit 이 실제로 내는 것들의 스키마 버전입니다."""
    clock, store, reader, events, notifier, tracer, run_id, _ = _harness(
        definition=_definition(tools=["calculator"])
    )
    gateway = FakeModelGateway(
        [
            ModelResponse(
                tool_calls=[
                    ToolCall(id="call_1", name="calculator", arguments={"expression": "1+1"})
                ],
                finish_reason="tool_calls",
            ),
            ModelResponse(text="2 입니다.", finish_reason="stop"),
        ]
    )
    usecase = _usecase(
        gateway=gateway,
        store=store,
        reader=reader,
        events=events,
        notifier=notifier,
        tracer=tracer,
        clock=clock,
    )

    usecase(run_id)

    seqs = [e.seq for e in events.published]
    assert seqs == list(range(1, len(seqs) + 1))
    assert events.published[-1].type == "run.finished"
    assert all(e.v == 1 for e in events.published)


def test_status_message_seq_matches_run_status_event_seq() -> None:
    """spec 0002 2.4 투영, 2.18: `StatusMessage.seq` 는 대응하는 `run.status` 이벤트의
    `seq` 와 같습니다."""
    clock, store, reader, events, notifier, tracer, run_id, _ = _harness()
    gateway = FakeModelGateway([ModelResponse(text="ok", finish_reason="stop")])
    usecase = _usecase(
        gateway=gateway,
        store=store,
        reader=reader,
        events=events,
        notifier=notifier,
        tracer=tracer,
        clock=clock,
    )

    usecase(run_id)

    status_events = [e for e in events.published if e.type == "run.status"]
    assert len(status_events) == len(notifier.messages)
    for event, message in zip(status_events, notifier.messages, strict=True):
        assert event.seq == message.seq
        assert event.payload["status"] == message.status.value


def test_started_at_and_finished_at_are_recorded_from_fake_clock() -> None:
    """spec 0002 2.4, D-10: `started_at`/`finished_at` 이 `FakeClock` 값으로 기록됩니다."""
    clock, store, reader, events, notifier, tracer, run_id, _ = _harness()
    gateway = FakeModelGateway([ModelResponse(text="ok", finish_reason="stop")])
    usecase = _usecase(
        gateway=gateway,
        store=store,
        reader=reader,
        events=events,
        notifier=notifier,
        tracer=tracer,
        clock=clock,
    )
    expected_started = clock.now()

    usecase(run_id)

    assert store.started_at(run_id) == expected_started
    assert store.finished_at(run_id) is not None
    final_message = notifier.messages[-1]
    assert final_message.started_at == expected_started
    assert final_message.finished_at == store.finished_at(run_id)


def test_terminal_run_releases_the_lease() -> None:
    """spec 0002 D-10: 종결 시 lease 를 `release` 합니다 — 다른 owner 가 곧바로 잡을
    수 있어야 합니다(다만 이 unit 은 종결 재개를 재발행으로 처리하므로, 여기서는
    fake store 의 내부 lease 소유자가 비워졌는지로 확인합니다)."""
    clock, store, reader, events, notifier, tracer, run_id, _ = _harness()
    gateway = FakeModelGateway([ModelResponse(text="ok", finish_reason="stop")])
    usecase = _usecase(
        gateway=gateway,
        store=store,
        reader=reader,
        events=events,
        notifier=notifier,
        tracer=tracer,
        clock=clock,
    )

    usecase(run_id)

    acquired_by_other = store.acquire_lease(run_id, owner="worker-other", ttl_seconds=60)
    assert acquired_by_other is True


def test_queued_run_with_cancel_already_requested_transitions_directly_to_cancelled() -> None:
    """리뷰 A, spec 0002 2.4: 집었을 때 `cancel_requested_at` 이 이미 있으면
    `queued -> cancelled` 로 **직접** 전이합니다 — `running` 을 거치지 않고, 실행을
    시작하지 않았으므로 `started_at` 은 `None` 입니다."""
    clock, store, reader, events, notifier, tracer, run_id, _ = _harness()
    reader.set_cancel_requested(run_id, clock.now())
    gateway = FakeModelGateway([])
    usecase = _usecase(
        gateway=gateway,
        store=store,
        reader=reader,
        events=events,
        notifier=notifier,
        tracer=tracer,
        clock=clock,
    )

    status = usecase(run_id)

    assert status == RunStatus.CANCELLED
    statuses = [e.payload["status"] for e in events.published if e.type == "run.status"]
    assert statuses == [RunStatus.CANCELLED.value]
    assert len(notifier.messages) == 1
    assert notifier.messages[0].status == RunStatus.CANCELLED
    assert notifier.messages[0].started_at is None
    assert store.started_at(run_id) is None
    assert gateway.calls == []


def test_task_is_recorded_for_every_model_call_even_without_tool_calls() -> None:
    """리뷰 D, spec 0002 D-5: `Task` 는 모델 호출마다 하나 — 도구 호출이 없는
    단계에서도 `tasks` 에 (빈 `tool_calls` 로) 기록됩니다."""
    clock, store, reader, events, notifier, tracer, run_id, _ = _harness()
    gateway = FakeModelGateway([ModelResponse(text="ok", finish_reason="stop")])
    usecase = _usecase(
        gateway=gateway,
        store=store,
        reader=reader,
        events=events,
        notifier=notifier,
        tracer=tracer,
        clock=clock,
    )

    usecase(run_id)

    saved = store.load(run_id)
    assert saved is not None
    assert len(saved.tasks) == 1
    assert saved.tasks[0].tool_calls == []
    task_started = next(e for e in events.published if e.type == "task.started")
    task_finished = next(e for e in events.published if e.type == "task.finished")
    assert task_started.payload["task_id"] == saved.tasks[0].task_id
    assert task_finished.payload["task_id"] == saved.tasks[0].task_id
