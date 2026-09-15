"""spec 0002 2.9, 2.18, R-5, AR-9 (P1-8): `RequestRun` 유스케이스가 `run.request`
span 을 만들고 그 span 이 낸 `traceparent` 를 `RunNotifier.requested` 에 실어 보내는
outbound 포트. `opentelemetry` 는 이 포트의 어댑터(`adapters/outbound`)에만 있습니다
(AR-9) — 이 포트 자체와 유스케이스는 그것을 모릅니다.
"""

from __future__ import annotations

from collections.abc import Mapping
from contextlib import AbstractContextManager
from typing import Protocol


class RequestTracing(Protocol):
    def span(self, name: str, attributes: Mapping[str, str]) -> AbstractContextManager[None]: ...

    def current_traceparent(self) -> str | None: ...
