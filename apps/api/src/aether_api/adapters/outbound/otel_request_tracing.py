"""spec 0002 2.9, 2.18, R-5, AR-9 (P1-8): `RequestTracing` 포트의 OpenTelemetry
구현. `opentelemetry` 는 이 파일에만 있습니다.

전역 `TracerProvider` 는 여기서 등록하지 않습니다(한 프로세스에 한 번만 허용) —
`provider` 를 넘기지 않으면 그 시점의 전역 provider(`init_telemetry` 가 등록해 둔
것)를 씁니다. `current_traceparent()` 는 활성 span 을 W3C `traceparent` 문자열로
인코딩합니다(`TraceContextTextMapPropagator` 로 — 직접 문자열을 조립하지 않습니다).
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from contextlib import contextmanager

from opentelemetry import trace
from opentelemetry.trace import TracerProvider
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

_propagator = TraceContextTextMapPropagator()


class OtelRequestTracing:
    """`RequestTracing` 포트의 OpenTelemetry 구현(spec 0002 2.9, 2.18)."""

    def __init__(
        self,
        provider: TracerProvider | None = None,
        *,
        instrumentation_name: str = "aether.api",
    ) -> None:
        resolved_provider = provider if provider is not None else trace.get_tracer_provider()
        self._tracer = resolved_provider.get_tracer(instrumentation_name)

    @contextmanager
    def span(self, name: str, attributes: Mapping[str, str]) -> Iterator[None]:
        with self._tracer.start_as_current_span(name, attributes=dict(attributes)):
            yield

    def current_traceparent(self) -> str | None:
        context = trace.get_current_span().get_span_context()
        if not context.is_valid:
            return None
        carrier: dict[str, str] = {}
        _propagator.inject(carrier)
        return carrier.get("traceparent")
