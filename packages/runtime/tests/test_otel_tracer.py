"""spec 0002 2.1, 2.9, R-5, AR-9: `OtelTracer` — `Tracer` 포트의 OpenTelemetry 구현.

(a) 부모–자식과 속성이 그대로 보존됩니다. (b) `current_trace_id()` 는 span 안에서
32자리 소문자 hex(그 span 의 trace id 와 동일), 밖에서는 `None`. (c) span 본문이
예외를 던지면 span 이 끝나고(`end_time` 존재) status 가 ERROR 이며 예외는 전파됩니다.
(d) 2.9 의 본문 금지: `ExecuteRunUseCase` 를 이 어댑터 + P1-4 fake 들로 조립해 도구
1회 호출 시나리오를 돌린 뒤, 모든 span 의 모든 속성 값에 system_prompt·user 입력·
모델 응답 텍스트·`reasoning` 문자열이 없고 span 이름 집합이 `{"run","task",
"model.complete","tool.run"}` 을 포함합니다.

전역 `TracerProvider` 는 여기서 설정하지 않습니다 — 매 테스트가 독립된
`TracerProvider() + SimpleSpanProcessor(InMemorySpanExporter())` 를 만들어 `OtelTracer`
에 직접 주입합니다(한 프로세스에 전역 provider 는 한 번만 허용되므로).
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

import pytest
from aether_runtime.adapters.outbound.model_gateway.fake import FakeModelGateway
from aether_runtime.adapters.outbound.telemetry.otel_tracer import OtelTracer
from aether_runtime.adapters.outbound.tools.registry import InMemoryToolRegistry
from aether_runtime.application.ports.outbound.model_gateway import ModelResponse
from aether_runtime.application.ports.outbound.run_declaration_reader import RunDeclaration
from aether_runtime.application.usecases.execute_run import ExecuteRunUseCase
from aether_runtime.domain.run import RunStatus
from aether_runtime.domain.tools import ToolCall
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import StatusCode

from packages.runtime.tests.fakes import (
    FakeClock,
    FakeEventSink,
    FakeRunDeclarationReader,
    FakeRunStateStore,
    FakeStatusNotifier,
)

_SYSTEM_PROMPT = "You are a secret-keeping helpful test agent."
_PROMPT_INPUT = "2 더하기 2 를 계산기로 계산해줘"
_FINAL_TEXT = "답은 4 입니다."
_REASONING = "내부 사고 과정: 사용자는 계산기를 원한다."


def _provider_and_exporter() -> tuple[TracerProvider, InMemorySpanExporter]:
    provider = TracerProvider()
    exporter = InMemorySpanExporter()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    return provider, exporter


def test_span_parent_child_and_attributes_are_preserved() -> None:
    provider, exporter = _provider_and_exporter()
    tracer = OtelTracer(provider)

    with tracer.span("run", {"aether.run_id": "r1"}):
        with tracer.span("task", {"aether.task_id": "t1"}):
            with tracer.span("model.complete", {"aether.model.id": "m1"}):
                pass

    spans = {span.name: span for span in exporter.get_finished_spans()}
    assert dict(spans["run"].attributes or {}) == {"aether.run_id": "r1"}
    assert dict(spans["task"].attributes or {}) == {"aether.task_id": "t1"}
    assert dict(spans["model.complete"].attributes or {}) == {"aether.model.id": "m1"}

    assert spans["run"].context is not None
    assert spans["task"].parent is not None
    assert spans["task"].parent.span_id == spans["run"].context.span_id
    assert spans["model.complete"].parent is not None
    assert spans["model.complete"].parent.span_id == spans["task"].context.span_id
    assert spans["task"].context.trace_id == spans["run"].context.trace_id
    assert spans["model.complete"].context.trace_id == spans["run"].context.trace_id


def test_current_trace_id_is_32_hex_inside_span_and_none_outside() -> None:
    provider, exporter = _provider_and_exporter()
    tracer = OtelTracer(provider)

    assert tracer.current_trace_id() is None

    observed: str | None = None
    with tracer.span("run", {}):
        observed = tracer.current_trace_id()

    assert tracer.current_trace_id() is None
    assert observed is not None
    assert len(observed) == 32
    assert observed == observed.lower()
    int(observed, 16)  # 유효한 hex — 아니면 ValueError

    (span,) = exporter.get_finished_spans()
    assert format(span.context.trace_id, "032x") == observed


def test_exception_in_span_body_ends_span_with_error_status_and_propagates() -> None:
    provider, exporter = _provider_and_exporter()
    tracer = OtelTracer(provider)

    class _Boom(Exception):
        pass

    with pytest.raises(_Boom):
        with tracer.span("run", {}):
            raise _Boom("boom")

    (span,) = exporter.get_finished_spans()
    assert span.end_time is not None
    assert span.status.status_code == StatusCode.ERROR


def _definition() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "system_prompt": _SYSTEM_PROMPT,
        "model": {"id": "test-model"},
        "tools": ["calculator"],
        "policy": {"timeout_seconds": 120, "max_steps": 8, "model_retries": 0, "tool_retries": 0},
    }


def test_span_tree_has_no_prompt_or_response_bodies_in_attributes() -> None:
    provider, exporter = _provider_and_exporter()
    tracer = OtelTracer(provider)

    run_id = uuid4()
    agent_version_id = uuid4()
    clock = FakeClock()
    store = FakeRunStateStore(clock)
    reader = FakeRunDeclarationReader(
        {
            run_id: RunDeclaration(
                run_id=run_id, agent_version_id=agent_version_id, input=_PROMPT_INPUT
            )
        },
        {agent_version_id: _definition()},
    )
    gateway = FakeModelGateway(
        [
            ModelResponse(
                tool_calls=[
                    ToolCall(id="call_1", name="calculator", arguments={"expression": "2+2"})
                ],
                reasoning=_REASONING,
                finish_reason="tool_calls",
            ),
            ModelResponse(text=_FINAL_TEXT, finish_reason="stop"),
        ]
    )
    usecase = ExecuteRunUseCase(
        store=store,
        declarations=reader,
        gateway=gateway,
        tools=InMemoryToolRegistry(clock),
        events=FakeEventSink(),
        notifier=FakeStatusNotifier(),
        tracer=tracer,
        clock=clock,
        owner="worker-otel",
    )

    status = usecase(run_id)

    assert status == RunStatus.SUCCEEDED

    spans = exporter.get_finished_spans()
    names = {span.name for span in spans}
    assert {"run", "task", "model.complete", "tool.run"} <= names

    all_values = " ".join(
        str(value) for span in spans for value in (span.attributes or {}).values()
    )
    assert _SYSTEM_PROMPT not in all_values
    assert _PROMPT_INPUT not in all_values
    assert _FINAL_TEXT not in all_values
    assert _REASONING not in all_values
    assert "2+2" not in all_values
