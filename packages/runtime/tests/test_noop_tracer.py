"""spec 0002 2.1, 2.9, AR-9 (P1-5a): `NoopTracer` — `Tracer` 포트의 프로덕션 no-op
구현. P1-8 이 OpenTelemetry 구현으로 교체하기 전까지 worker `main.py` 가 조립에
씁니다. span 은 아무것도 기록하지 않고 예외를 전파만 합니다; `current_trace_id` 는
항상 `None` 입니다.
"""

from __future__ import annotations

import pytest
from aether_runtime.adapters.outbound.telemetry.noop_tracer import NoopTracer


def test_span_executes_the_body_and_returns_none_trace_id() -> None:
    tracer = NoopTracer()
    entered = False

    with tracer.span("run", {"aether.run_id": "r1"}):
        entered = True

    assert entered is True
    assert tracer.current_trace_id() is None


def test_span_propagates_exceptions_from_the_body() -> None:
    tracer = NoopTracer()

    with pytest.raises(ValueError), tracer.span("run", {}):
        raise ValueError("boom")
