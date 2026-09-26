"""spec 0003 2.4, D-6, 개정 4: 판정 값 — `allow` 아니면 `deny`, 제3의 값 없음.

`aether_policy.domain` 은 표준 라이브러리만 씁니다(AR-9) — 프레임워크·I/O 없음.
"""

from __future__ import annotations

from typing import Literal

Decision = Literal["allow", "deny"]
