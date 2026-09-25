"""spec 0002 2.2, 2.7, D-4(AD-2 결함 수정): `RunExists` 인바운드 포트 인터페이스.

HTTP 어댑터(`adapters/inbound/http/events.py`)는 SSE 스트림을 열기 전에 Run 의
존재만 먼저 확인하려고 이 포트를 씁니다(AR-12) — 이벤트가 하나도 없어도(아직
`queued`) 확인할 수 있어야, 응답 헤더를 그 확인만으로 곧장 낼 수 있고 그 뒤의
idle 구간이 keep-alive 로 보호됩니다. 구현(`application/usecases/run_exists.py`)은
조립(`main.py`)이 건네줍니다.
"""

from __future__ import annotations

from typing import Protocol
from uuid import UUID


class RunExists(Protocol):
    """`run_id` 의 Run 이 있으면 `True`. 이벤트 유무와 무관합니다."""

    def __call__(self, run_id: UUID) -> bool: ...
