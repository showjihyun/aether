"""spec 0002 2.1, 2.9, R-5, AR-9 (P1-8): `OtelTracer` — `Tracer` 포트의 OpenTelemetry
구현. `opentelemetry` 는 이 디렉터리 안에서만 씁니다.

전역 `TracerProvider` 는 여기서 등록하지 않습니다 — OpenTelemetry 는 한 프로세스에서
`trace.set_tracer_provider` 를 한 번만 허용합니다. `provider` 를 넘기지 않으면 그
시점의 전역 provider(`opentelemetry.trace.get_tracer_provider()` — 보통
`apps/*/adapters/outbound/telemetry.py` 의 `init_telemetry` 가 등록해 둔 것)를
씁니다. 테스트는 독립된 `TracerProvider() + SimpleSpanProcessor(InMemorySpanExporter())`
를 만들어 직접 주입합니다.

`current_trace_id()` 는 현재 활성 span(어느 tracer 로 열렸든, ambient
`opentelemetry.context`)을 봅니다 — 유효하지 않으면(활성 span 없음) `None`.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from contextlib import contextmanager

from opentelemetry import trace
from opentelemetry.trace import TracerProvider


class OtelTracer:
    """`Tracer` 포트의 OpenTelemetry 구현(spec 0002 2.9)."""

    def __init__(
        self,
        provider: TracerProvider | None = None,
        *,
        instrumentation_name: str = "aether.runtime",
    ) -> None:
        resolved_provider = provider if provider is not None else trace.get_tracer_provider()
        self._tracer = resolved_provider.get_tracer(instrumentation_name)

    @contextmanager
    def span(self, name: str, attributes: Mapping[str, str]) -> Iterator[None]:
        with self._tracer.start_as_current_span(name, attributes=dict(attributes)):
            yield

    def current_trace_id(self) -> str | None:
        context = trace.get_current_span().get_span_context()
        if not context.is_valid:
            return None
        return format(context.trace_id, "032x")
