"""spec 0002 2.9, 2.18, R-5, AR-9 (P1-8): `OtelRequestTracing` — `RequestTracing`
포트의 OpenTelemetry 구현.

span 안에서 W3C 형식(`00-<trace_id 32hex>-<span_id 16hex>-<flags 2hex>`)의
`traceparent` 를 내고, 그 trace id 가 exporter 가 낸 같은 span 의 trace id 와
같습니다. span 밖에서는 `None`.

전역 `TracerProvider` 를 설정하지 않습니다 — 독립된 `TracerProvider` 를 만들어
어댑터에 직접 주입합니다.
"""

from __future__ import annotations

import re

from aether_api.adapters.outbound.otel_request_tracing import OtelRequestTracing
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

_TRACEPARENT_RE = re.compile(r"00-([0-9a-f]{32})-([0-9a-f]{16})-[0-9a-f]{2}")


def _provider_and_exporter() -> tuple[TracerProvider, InMemorySpanExporter]:
    provider = TracerProvider()
    exporter = InMemorySpanExporter()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    return provider, exporter


def test_current_traceparent_is_none_outside_a_span() -> None:
    provider, _exporter = _provider_and_exporter()
    tracing = OtelRequestTracing(provider)

    assert tracing.current_traceparent() is None


def test_span_yields_w3c_traceparent_matching_the_exported_span() -> None:
    provider, exporter = _provider_and_exporter()
    tracing = OtelRequestTracing(provider)

    observed: str | None = None
    with tracing.span("run.request", {"aether.agent_id": "a1"}):
        observed = tracing.current_traceparent()

    assert tracing.current_traceparent() is None
    assert observed is not None
    match = _TRACEPARENT_RE.fullmatch(observed)
    assert match is not None, observed

    (span,) = exporter.get_finished_spans()
    assert span.name == "run.request"
    assert dict(span.attributes or {}) == {"aether.agent_id": "a1"}
    assert match.group(1) == format(span.context.trace_id, "032x")
    assert match.group(2) == format(span.context.span_id, "016x")
