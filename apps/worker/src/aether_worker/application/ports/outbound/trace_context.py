"""spec 0002 2.9 예약 (P1-5a, P1-8 이 OTel 로 채움): `TraceContext` — 복원한
`traceparent` 를 현재 실행 컨텍스트에 심는 outbound 포트.

P1-5a 의 `NoopTraceContext` 는 아무 일도 하지 않습니다 — 실제 OTel 전파(부모
span 복원)는 P1-8 이 합니다. 그때까지 `execute_run` 이 만드는 span 은 새 trace 로
시작합니다.
"""

from __future__ import annotations

from contextlib import AbstractContextManager
from typing import Protocol


class TraceContext(Protocol):
    def activate(self, traceparent: str | None) -> AbstractContextManager[None]: ...
