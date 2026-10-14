"""spec 0005 2.3: `Clock` — 시간은 이 포트를 지납니다(AR-9). 이 패키지는 `now()` 하나만 씁니다."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol


class Clock(Protocol):
    def now(self) -> datetime: ...
