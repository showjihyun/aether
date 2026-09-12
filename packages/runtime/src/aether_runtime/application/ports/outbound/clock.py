"""spec 0002 2.1, R-4, R-11: `Clock` — 시간은 전부 이 포트를 지납니다.

`domain`·`application` 은 `datetime.now()`/`time.monotonic()`/`time.sleep()` 을 직접
부르지 않습니다(AR-9) — 대신 이 포트로 시간을 요청해 테스트가 `FakeClock` 으로
대체할 수 있게 합니다.
"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol


class Clock(Protocol):
    def now(self) -> datetime: ...

    def monotonic(self) -> float: ...

    def sleep(self, seconds: float) -> None: ...
