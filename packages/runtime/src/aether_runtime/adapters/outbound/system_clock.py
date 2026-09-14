"""spec 0002 2.1, R-4: `SystemClock` — `Clock` 포트의 프로덕션 구현.

`domain`·`application` 은 `datetime.now()`/`time.monotonic()`/`time.sleep()` 을 직접
쓰지 않습니다(AR-9) — 이 어댑터가 실제 시간을 대신 요청받습니다. 테스트는
`packages/runtime/tests/fakes.py` 의 `FakeClock` 을 씁니다.
"""

from __future__ import annotations

import time
from datetime import UTC, datetime


class SystemClock:
    """`Clock` 포트의 실제 벽시계·단조 시계·`sleep` 구현."""

    def now(self) -> datetime:
        return datetime.now(UTC)

    def monotonic(self) -> float:
        return time.monotonic()

    def sleep(self, seconds: float) -> None:
        time.sleep(seconds)
