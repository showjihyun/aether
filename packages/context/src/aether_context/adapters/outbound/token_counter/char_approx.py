"""spec 0004 D-6, C-2: `TokenCounter`(outbound) 의 유일한 구현 — 문자 ÷ 4 를
**올림**합니다. 토크나이저 의존을 들이지 않고, 어긋남을 항상 과대 추정 방향으로
고정합니다 — 버림이었다면 실제 토큰 수를 과소평가할 수 있지만, 올림은
`tokens * 4 >= len(text)` 를 항상 보장합니다.
"""

from __future__ import annotations

import math


class CharApproxTokenCounter:
    def count(self, text: str) -> int:
        if not text:
            return 0
        return math.ceil(len(text) / 4)
