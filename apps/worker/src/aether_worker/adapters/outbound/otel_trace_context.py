"""spec 0002 2.9 (P1-8): `TraceContext` 의 OpenTelemetry 구현. 복원한 `traceparent`
를 현재 실행 컨텍스트에 심어, 그 컨텍스트 안에서 여는 span 이 그 값을 부모로 삼게
합니다(W3C Trace Context, `opentelemetry.context.attach`/`detach`).

`traceparent` 가 `None`/`""`/파싱 불가능한 문자열이면 `TraceContextTextMapPropagator.
extract` 가 예외 없이 입력 컨텍스트를 그대로 돌려주므로(전파할 부모가 없음), 그
안에서 여는 span 은 새 root 가 됩니다 — 문자열 형식을 이 파일이 직접 검사하지
않습니다.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from opentelemetry import context as otel_context
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

_propagator = TraceContextTextMapPropagator()


class OtelTraceContext:
    """`TraceContext` 포트의 OpenTelemetry 구현(spec 0002 2.9)."""

    @contextmanager
    def activate(self, traceparent: str | None) -> Iterator[None]:
        carrier = {"traceparent": traceparent} if traceparent else {}
        extracted = _propagator.extract(carrier=carrier)
        token = otel_context.attach(extracted)
        try:
            yield
        finally:
            otel_context.detach(token)
