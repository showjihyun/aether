"""spec 0002 2.2, 2.7, D-4: `ReadRunEvents` 인바운드 포트 인터페이스.

HTTP 어댑터(`adapters/inbound/http/events.py`)는 이 포트 타입만 보고 부릅니다
(AR-12) — 구현(`application/usecases/read_run_events.py`)은 조립(`main.py`)이
건네줍니다.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Protocol
from uuid import UUID

from aether_runtime.domain.events import RunEvent


class ReadRunEvents(Protocol):
    """`run_id` 의 이벤트를 `seq` 순으로 냅니다(2.7).

    `after_seq` 가 주어지면(`Last-Event-ID` 헤더) 그 값보다 큰 `seq` 부터 재개합니다.
    Run 이 없으면 `aether_api.domain.run.RunNotFound` 를 던집니다.
    """

    def __call__(self, run_id: UUID, after_seq: int | None) -> AsyncIterator[RunEvent]: ...
