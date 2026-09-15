"""spec 0002 2.9, R-5: `OtelTraceContext` — 복원한 `traceparent` 를 현재 실행
컨텍스트에 심는 outbound 포트의 OpenTelemetry 구현.

(a) 부모 span 에서 뽑은 `traceparent` 로 `activate` 하면 그 안에서 연 span 이 같은
trace 에 속하고 부모 span id 가 그 부모의 span id 와 같습니다. (b) `None`/`""` 은
새 root(부모 없음). (c) 잘못된 문자열은 예외 없이 새 root. (d) 컨텍스트를 벗어나면
이전 컨텍스트로 복원됩니다 — 벗어난 뒤 연 span 은 부모가 없습니다.

전역 `TracerProvider` 를 설정하지 않습니다 — 독립된 `TracerProvider` 를 만들어
`OtelTracer` 에 직접 주입합니다.
"""

from __future__ import annotations

from aether_runtime.adapters.outbound.telemetry.otel_tracer import OtelTracer
from aether_worker.adapters.outbound.otel_trace_context import OtelTraceContext
from opentelemetry.sdk.trace import ReadableSpan, TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import NonRecordingSpan, set_span_in_context
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

_propagator = TraceContextTextMapPropagator()


def _provider_and_tracer() -> tuple[InMemorySpanExporter, OtelTracer]:
    provider = TracerProvider()
    exporter = InMemorySpanExporter()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    return exporter, OtelTracer(provider)


def _traceparent_for(span: ReadableSpan) -> str:
    """끝난 span 의 context 로 W3C `traceparent` 문자열을 만듭니다(OTel propagator 경유,
    직접 조립하지 않습니다) — `NonRecordingSpan` 은 이미 끝난 span 의 context 를
    "현재 span" 인 것처럼 컨텍스트에 담아 `inject` 가 읽게 하는 표준 방법입니다."""
    carrier: dict[str, str] = {}
    context = set_span_in_context(NonRecordingSpan(span.context))
    _propagator.inject(carrier, context=context)
    return carrier["traceparent"]


def test_activate_traceparent_makes_child_share_trace_and_parent_span() -> None:
    exporter, tracer = _provider_and_tracer()
    trace_context = OtelTraceContext()

    with tracer.span("parent-run", {}):
        pass
    (parent_span,) = exporter.get_finished_spans()
    traceparent = _traceparent_for(parent_span)
    assert traceparent.startswith("00-")

    with trace_context.activate(traceparent):
        with tracer.span("child-run", {}):
            pass

    child_span = next(s for s in exporter.get_finished_spans() if s.name == "child-run")
    assert child_span.context.trace_id == parent_span.context.trace_id
    assert child_span.parent is not None
    assert child_span.parent.span_id == parent_span.context.span_id


def test_activate_none_or_empty_starts_a_new_root() -> None:
    exporter, tracer = _provider_and_tracer()
    trace_context = OtelTraceContext()

    with trace_context.activate(None):
        with tracer.span("root-a", {}):
            pass
    with trace_context.activate(""):
        with tracer.span("root-b", {}):
            pass

    spans = {s.name: s for s in exporter.get_finished_spans()}
    assert spans["root-a"].parent is None
    assert spans["root-b"].parent is None


def test_activate_garbage_string_raises_no_exception_and_starts_new_root() -> None:
    exporter, tracer = _provider_and_tracer()
    trace_context = OtelTraceContext()

    with trace_context.activate("garbage"):
        with tracer.span("root-garbage", {}):
            pass

    (span,) = exporter.get_finished_spans()
    assert span.parent is None


def test_leaving_activate_restores_previous_context() -> None:
    exporter, tracer = _provider_and_tracer()
    trace_context = OtelTraceContext()

    with tracer.span("parent-run", {}):
        pass
    (parent_span,) = exporter.get_finished_spans()
    traceparent = _traceparent_for(parent_span)

    with trace_context.activate(traceparent):
        pass

    with tracer.span("after-activate", {}):
        pass

    after_span = next(s for s in exporter.get_finished_spans() if s.name == "after-activate")
    assert after_span.parent is None
