"""D-17 (MVP-2d): `ExecuteRunUseCase` 가 모델 호출을 `stream` 으로 하고 텍스트 조각마다
`model.delta` 를 발행한다. 재시도는 조각을 내기 전에만.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID, uuid4

from aether_runtime.adapters.outbound.model_gateway.fake import FakeModelGateway
from aether_runtime.application.ports.outbound.model_gateway import (
    ModelDelta,
    ModelError,
    ModelGateway,
    ModelRequest,
    ModelResponse,
)
from aether_runtime.application.ports.outbound.run_declaration_reader import RunDeclaration
from aether_runtime.application.usecases.execute_run import ExecuteRunUseCase
from aether_runtime.domain.events import RunEvent
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
    FakeToolGateway,
    InMemoryTracer,
)


@dataclass
class _Status:
    lost: bool = False


def _build(
    gateway: ModelGateway,
    *,
    model_retries: int = 0,
    events: FakeEventSink | None = None,
    lease_keeper: Any = None,
) -> tuple[ExecuteRunUseCase, UUID, FakeEventSink, FakeClock]:
    run_id, agent_version_id = uuid4(), uuid4()
    definition: dict[str, Any] = {
        "schema_version": 1,
        "system_prompt": "test",
        "model": {"id": "m"},
        "tools": ["calculator"],
        "policy": {
            "timeout_seconds": 120,
            "max_steps": 8,
            "model_retries": model_retries,
            "tool_retries": 0,
        },
    }
    reader = FakeRunDeclarationReader(
        {run_id: RunDeclaration(run_id=run_id, agent_version_id=agent_version_id, input="hi")},
        {agent_version_id: definition},
    )
    clock = FakeClock()
    sink = events if events is not None else FakeEventSink()
    usecase = ExecuteRunUseCase(
        FakeRunStateStore(clock),
        reader,
        gateway,
        FakeToolGateway({"calculator": FakeTool(name="calculator")}),
        sink,
        FakeStatusNotifier(),
        InMemoryTracer(),
        clock,
        owner="w",
        lease_keeper=lease_keeper,
    )
    return usecase, run_id, sink, clock


def _run(
    gateway: ModelGateway, *, model_retries: int = 0
) -> tuple[RunStatus, FakeEventSink, FakeClock]:
    usecase, run_id, events, clock = _build(gateway, model_retries=model_retries)
    return usecase(run_id), events, clock


def _types(events: FakeEventSink) -> list[str]:
    return [e.type for e in events.published]


def _deltas(events: FakeEventSink) -> list[str]:
    return [e.payload["text"] for e in events.published if e.type == "model.delta"]


def test_answer_is_published_as_model_delta_between_task_started_and_model_completed() -> None:
    """D-17: 순서 task.started -> model.delta* -> model.completed, 조각을 이으면 답변."""
    gateway = FakeModelGateway([ModelResponse(text="four is the answer", finish_reason="stop")])

    status, events, _ = _run(gateway)

    assert status == RunStatus.SUCCEEDED
    types = _types(events)
    first = types.index("model.delta")
    last = len(types) - 1 - types[::-1].index("model.delta")
    assert types[first - 1] == "task.started"
    assert types[last + 1] == "model.completed"
    assert set(types[first : last + 1]) == {"model.delta"}
    assert "".join(_deltas(events)) == "four is the answer"
    assert len(_deltas(events)) == 4


def test_seq_stays_contiguous_from_one_with_deltas() -> None:
    """D-17: model.delta 가 끼어도 seq 는 1부터 건너뜀·중복 없이 증가한다."""
    gateway = FakeModelGateway([ModelResponse(text="a b c", finish_reason="stop")])

    _, events, _ = _run(gateway)

    seqs = [e.seq for e in events.published]
    assert seqs == list(range(1, len(seqs) + 1))
    assert events.published[-1].type == "run.finished"


def test_model_completed_payload_is_unchanged() -> None:
    """D-17: model.completed 는 여전히 {finish_reason, usage} 이고 complete 경로의 값."""
    usage = {"prompt_tokens": 7, "completion_tokens": 3}
    response = ModelResponse(text="x y", finish_reason="length", usage=usage)

    _, events, _ = _run(FakeModelGateway([response]))

    completed = [e.payload for e in events.published if e.type == "model.completed"]
    assert completed == [{"finish_reason": "length", "usage": usage}]


def test_tool_call_only_turn_emits_no_model_delta() -> None:
    """D-17: 텍스트 없는 도구 호출 턴에는 model.delta 가 없고, 도구 호출은 그대로 동작."""
    gateway = FakeModelGateway(
        [
            ModelResponse(
                tool_calls=[ToolCall(id="c1", name="calculator", arguments={})],
                finish_reason="tool_calls",
            ),
            ModelResponse(text="done", finish_reason="stop"),
        ]
    )

    status, events, _ = _run(gateway)

    assert status == RunStatus.SUCCEEDED
    assert _deltas(events) == ["done"]
    types = _types(events)
    assert types.index("tool.called") < types.index("model.delta")


def test_reasoning_is_not_published() -> None:
    """D-19, D-17: reasoning 조각은 이벤트로 나가지 않는다."""
    gateway = FakeModelGateway(
        [ModelResponse(text="ans", reasoning="secret thoughts", finish_reason="stop")]
    )

    _, events, _ = _run(gateway)

    assert _deltas(events) == ["ans"]
    assert "secret thoughts" not in repr([e.payload for e in events.published])


@dataclass
class _ScriptedStreamGateway:
    """호출마다 (조각들, 마지막에 던질 오류) 를 소비하는 스트림 전용 게이트웨이."""

    script: list[tuple[list[ModelDelta], ModelError | None]]
    calls: list[ModelRequest] = field(default_factory=list)

    def complete(self, request: ModelRequest) -> ModelResponse:
        raise AssertionError("execute_run must use stream")

    def stream(self, request: ModelRequest) -> Iterator[ModelDelta]:
        self.calls.append(request)
        deltas, error = self.script.pop(0)
        yield from deltas
        if error is not None:
            raise error

    def embed(self, texts: list[str]) -> list[list[float]]:
        raise NotImplementedError


def _ok(text: str) -> tuple[list[ModelDelta], None]:
    return [
        ModelDelta(text=text),
        ModelDelta(done=True, finish_reason="stop", usage=None),
    ], None


def test_failure_before_first_delta_is_retried() -> None:
    """D-17 따름 결정: 조각을 내기 전 실패는 지금처럼 재시도한다(호출 횟수)."""
    gateway = _ScriptedStreamGateway([([], ModelError(kind="http", status=500)), _ok("fine")])

    status, events, clock = _run(gateway, model_retries=1)

    assert status == RunStatus.SUCCEEDED
    assert len(gateway.calls) == 2
    assert clock.sleep_calls == [0.5]
    assert _deltas(events) == ["fine"]


def test_failure_after_a_delta_is_not_retried_and_answer_is_not_duplicated() -> None:
    """D-17 따름 결정: 조각을 낸 뒤 실패는 재시도 없이 failed(model_error), 답변은 한 번."""
    gateway = _ScriptedStreamGateway(
        [([ModelDelta(text="par")], ModelError(kind="http", status=500)), _ok("par tial")]
    )

    status, events, clock = _run(gateway, model_retries=2)

    assert status == RunStatus.FAILED
    assert len(gateway.calls) == 1
    assert clock.sleep_calls == []
    assert _deltas(events) == ["par"]
    final_status = [e.payload for e in events.published if e.type == "run.status"][-1]
    assert final_status["failure_reason"] == FailureReason.MODEL_ERROR.value
    seqs = [e.seq for e in events.published]
    assert seqs == list(range(1, len(seqs) + 1))


def test_stream_without_terminal_delta_is_a_protocol_error() -> None:
    """D-17: done 조각 없이 끝난 스트림은 잘린 응답이다 -- 조각 전이면 재시도 대상 protocol."""
    gateway = _ScriptedStreamGateway([([], None), _ok("fine")])

    status, _, _ = _run(gateway, model_retries=1)

    assert status == RunStatus.SUCCEEDED
    assert len(gateway.calls) == 2


def test_lease_is_held_for_the_whole_stream_consumption() -> None:
    """C-13: 스트림 소비 전체가 LeaseKeeper.keep 안에서 일어난다(조각 발행 시점 포함)."""
    inside: list[bool] = []
    state = {"open": False}

    class _Keeper:
        @contextmanager
        def keep(self, run_id: UUID, owner: str, ttl_seconds: float) -> Iterator[_Status]:
            state["open"] = True
            try:
                yield _Status()
            finally:
                state["open"] = False

    class _Sink(FakeEventSink):
        def publish(self, event: RunEvent) -> None:
            if event.type == "model.delta":
                inside.append(state["open"])
            super().publish(event)

    gateway = FakeModelGateway([ModelResponse(text="a b c", finish_reason="stop")])
    usecase, run_id, _, _ = _build(gateway, events=_Sink(), lease_keeper=_Keeper())

    assert usecase(run_id) == RunStatus.SUCCEEDED
    assert inside == [True, True, True]
