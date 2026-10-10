"""spec 0004 R-11, D-11, 2.7 (P3-5): `ContextReport` 의 숫자와 Run 의 종결 상태가
span 속성으로 올라가는지 인메모리 `Tracer` 로 증명합니다.

`context.*` 는 `model.complete` span 마다, `aether.run.status` 는 `run` span 에 붙습니다.
속성 값은 전부 문자열이고(spec 0002 2.9) 본문은 어디에도 없습니다(D-11).
"""

from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

from aether_runtime.adapters.outbound.model_gateway.fake import FakeModelGateway
from aether_runtime.application.ports.outbound.context_compiler import (
    ContextDrop,
    ContextReport,
    ContextSourceTokens,
)
from aether_runtime.application.ports.outbound.model_gateway import ModelResponse
from aether_runtime.application.ports.outbound.run_declaration_reader import RunDeclaration
from aether_runtime.application.usecases.execute_run import ExecuteRunUseCase
from aether_runtime.domain.run import RunStatus
from aether_runtime.domain.tools import ToolCall, ToolResult

from packages.runtime.tests.fakes import (
    FakeClock,
    FakeContextCompiler,
    FakeEventSink,
    FakeRunDeclarationReader,
    FakeRunStateStore,
    FakeStatusNotifier,
    FakeTool,
    FakeToolGateway,
    InMemoryTracer,
    SpanRecord,
)

_SYSTEM_PROMPT = "SECRET-SYSTEM-PROMPT-KPI"
_INPUT = "SECRET-USER-INPUT-KPI"
_ANSWER = "SECRET-MODEL-ANSWER-KPI"


def _definition(*, tools: list[str] | None = None, timeout_seconds: int = 120) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "system_prompt": _SYSTEM_PROMPT,
        "model": {"id": "test-model"},
        "tools": tools or [],
        "policy": {
            "timeout_seconds": timeout_seconds,
            "max_steps": 8,
            "model_retries": 0,
            "tool_retries": 0,
        },
    }


class _ClockAdvancingTool:
    name = "calculator"
    description = "advances the fake clock"
    input_schema: dict[str, Any] = {}

    def __init__(self, clock: FakeClock, seconds: float) -> None:
        self._clock = clock
        self._seconds = seconds

    def run(self, arguments: dict[str, Any]) -> ToolResult:
        del arguments
        self._clock.advance(self._seconds)
        return ToolResult(content="2")


def _run(
    responses: list[ModelResponse],
    *,
    definition: dict[str, Any] | None = None,
    report: ContextReport | None = None,
    tools: Any = None,
    clock: FakeClock | None = None,
    cancel_first: bool = False,
) -> tuple[RunStatus, InMemoryTracer]:
    clock = clock or FakeClock()
    run_id: UUID = uuid4()
    agent_version_id = uuid4()
    reader = FakeRunDeclarationReader(
        {run_id: RunDeclaration(run_id=run_id, agent_version_id=agent_version_id, input=_INPUT)},
        {agent_version_id: definition or _definition()},
    )
    if cancel_first:
        reader.set_cancel_requested(run_id, clock.now())
    tracer = InMemoryTracer()
    usecase = ExecuteRunUseCase(
        store=FakeRunStateStore(clock),
        declarations=reader,
        gateway=FakeModelGateway(responses),
        tools=tools or FakeToolGateway({"calculator": FakeTool(name="calculator")}),
        events=FakeEventSink(),
        notifier=FakeStatusNotifier(),
        tracer=tracer,
        clock=clock,
        owner="worker-kpi",
        context_compiler=FakeContextCompiler(report),
    )
    return usecase(run_id), tracer


def _spans(tracer: InMemoryTracer, name: str) -> list[SpanRecord]:
    return [span for span in tracer.spans if span.name == name]


def _stop() -> ModelResponse:
    return ModelResponse(text=_ANSWER, finish_reason="stop")


_FULL_REPORT = ContextReport(
    budget_tokens=100,
    source_tokens=(
        ContextSourceTokens(source="system", tokens=10),
        ContextSourceTokens(source="conversation", tokens=40),
        ContextSourceTokens(source="knowledge", tokens=30),
        ContextSourceTokens(source="memory", tokens=20),
        ContextSourceTokens(source="tools", tokens=0),
    ),
    total_tokens=100,
    dropped=(
        ContextDrop(source="memory", tokens=20),
        ContextDrop(source="knowledge", tokens=5),
    ),
)


def test_model_complete_span_carries_context_numbers_from_the_report() -> None:
    """spec 0004 R-11: 보고의 숫자가 이름 그대로 문자열 속성으로 올라갑니다."""
    status, tracer = _run([_stop()], report=_FULL_REPORT)

    assert status == RunStatus.SUCCEEDED
    (model_span,) = _spans(tracer, "model.complete")
    attrs = model_span.attributes
    assert attrs["context.tokens.system"] == "10"
    assert attrs["context.tokens.conversation"] == "40"
    assert attrs["context.tokens.knowledge"] == "30"
    assert attrs["context.tokens.memory"] == "20"
    assert attrs["context.tokens.tools"] == "0"
    assert attrs["context.tokens.total"] == "100"
    assert attrs["context.budget"] == "100"
    assert attrs["context.dropped.memory"] == "20"
    assert attrs["context.dropped.knowledge"] == "5"
    assert attrs["context.dropped.sources"] == "memory,knowledge"
    assert all(isinstance(value, str) for value in attrs.values())


def test_sources_absent_from_the_report_have_no_attribute_not_zero() -> None:
    """spec 0004 R-11: 없는 소스는 `"0"` 이 아니라 속성 자체가 없습니다 — 없었다와
    비용이 0 이었다는 다른 말입니다. 빼지 않았으면 `dropped.*` 도 없습니다."""
    report = ContextReport(
        budget_tokens=50,
        source_tokens=(
            ContextSourceTokens(source="system", tokens=5),
            ContextSourceTokens(source="conversation", tokens=7),
        ),
        total_tokens=12,
    )

    _status, tracer = _run([_stop()], report=report)

    (model_span,) = _spans(tracer, "model.complete")
    attrs = model_span.attributes
    assert attrs["context.tokens.system"] == "5"
    assert attrs["context.tokens.total"] == "12"
    assert attrs["context.budget"] == "50"
    for absent in ("knowledge", "memory", "tools"):
        assert f"context.tokens.{absent}" not in attrs
    assert not [key for key in attrs if key.startswith("context.dropped")]


def test_total_and_budget_are_always_present_even_for_an_empty_report() -> None:
    """spec 0004 R-11: 보고가 비어 있어도 합계와 예산은 올라갑니다."""
    _status, tracer = _run([_stop()], report=ContextReport(budget_tokens=8192))

    (model_span,) = _spans(tracer, "model.complete")
    assert model_span.attributes["context.tokens.total"] == "0"
    assert model_span.attributes["context.budget"] == "8192"


def test_context_attributes_are_attached_to_every_model_complete_span() -> None:
    """spec 0004 2.7: compile 은 스텝마다 일어나므로 속성도 model.complete span 마다 붙고,
    다른 span 에는 붙지 않습니다."""
    responses = [
        ModelResponse(
            tool_calls=[ToolCall(id="c1", name="calculator", arguments={})],
            finish_reason="tool_calls",
        ),
        _stop(),
    ]

    _status, tracer = _run(
        responses, definition=_definition(tools=["calculator"]), report=_FULL_REPORT
    )

    model_spans = _spans(tracer, "model.complete")
    assert len(model_spans) == 2
    assert all(span.attributes.get("context.tokens.total") == "100" for span in model_spans)
    others = [span for span in tracer.spans if span.name != "model.complete"]
    assert not [key for span in others for key in span.attributes if key.startswith("context.")]


def test_no_body_text_appears_in_any_span_attribute() -> None:
    """spec 0004 D-11: 프롬프트·입력·응답 본문이 어느 속성 값에도 없습니다."""
    _status, tracer = _run([_stop()], report=_FULL_REPORT)

    values = " ".join(value for span in tracer.spans for value in span.attributes.values())
    for secret in (_SYSTEM_PROMPT, _INPUT, _ANSWER):
        assert secret not in values


def test_run_span_carries_succeeded_status() -> None:
    """spec 0004 2.7: Task Success 는 Run 의 종결 상태에서 옵니다."""
    status, tracer = _run([_stop()])

    assert status == RunStatus.SUCCEEDED
    (run_span,) = _spans(tracer, "run")
    assert run_span.attributes.get("aether.run.status") == "succeeded"


def test_run_span_carries_failed_status() -> None:
    """spec 0004 2.7: 정의에 없는 도구 호출 -> failed."""
    ghost = ModelResponse(
        tool_calls=[ToolCall(id="c1", name="ghost", arguments={})], finish_reason="tool_calls"
    )

    status, tracer = _run([ghost])

    assert status == RunStatus.FAILED
    (run_span,) = _spans(tracer, "run")
    assert run_span.attributes.get("aether.run.status") == "failed"


def test_run_span_carries_cancelled_status() -> None:
    """spec 0004 2.7: 시작 전에 취소가 요청된 Run -> cancelled."""
    status, tracer = _run([_stop()], cancel_first=True)

    assert status == RunStatus.CANCELLED
    (run_span,) = _spans(tracer, "run")
    assert run_span.attributes.get("aether.run.status") == "cancelled"


def test_run_span_carries_timed_out_status() -> None:
    """spec 0004 2.7: 도구가 예산을 다 쓰면 다음 단계 시작에서 timed_out."""
    clock = FakeClock()
    responses = [
        ModelResponse(
            tool_calls=[ToolCall(id="c1", name="calculator", arguments={})],
            finish_reason="tool_calls",
        ),
        _stop(),
    ]
    tools = FakeToolGateway({"calculator": _ClockAdvancingTool(clock, 61.0)})

    status, tracer = _run(
        responses,
        definition=_definition(tools=["calculator"], timeout_seconds=60),
        tools=tools,
        clock=clock,
    )

    assert status == RunStatus.TIMED_OUT
    (run_span,) = _spans(tracer, "run")
    assert run_span.attributes.get("aether.run.status") == "timed_out"
