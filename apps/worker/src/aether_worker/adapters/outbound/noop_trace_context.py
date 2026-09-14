"""spec 0002 2.9 예약 (P1-5a): `TraceContext` 의 no-op 구현. `main.py` 가 P1-8 전까지
조립에 씁니다 — `traceparent` 를 실제로 전파하지 않습니다(OTel 실제 전파는 P1-8).
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager


class NoopTraceContext:
    @contextmanager
    def activate(self, traceparent: str | None) -> Iterator[None]:
        del traceparent
        yield
