"""spec 0002 2.1, 2.9, R-5: `Tracer` — 유스케이스는 이 포트로만 span 을 만듭니다.

`opentelemetry` 는 `adapters/outbound/telemetry`(P1-8)에만 있습니다(AR-9). 속성 값은
전부 문자열입니다 — 프롬프트·응답·`reasoning` 본문은 여기 넣지 않습니다(2.9).
"""

from __future__ import annotations

from collections.abc import Mapping
from contextlib import AbstractContextManager
from typing import Protocol


class Tracer(Protocol):
    def span(self, name: str, attributes: Mapping[str, str]) -> AbstractContextManager[None]: ...

    def current_trace_id(self) -> str | None: ...
