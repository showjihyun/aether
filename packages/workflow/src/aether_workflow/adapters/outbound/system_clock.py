"""spec 0005: `SystemClock` - `Clock` 포트의 프로덕션 구현. 이 패키지의 `domain`·`application`
은 `datetime.now()` 를 직접 부르지 않습니다(AR-9) - 이 어댑터가 대신 요청받습니다.
"""

from __future__ import annotations

from datetime import UTC, datetime


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(UTC)
