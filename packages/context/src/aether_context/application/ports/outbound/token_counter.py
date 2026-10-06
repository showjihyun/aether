"""spec 0004 D-6, 2.2: `TokenCounter` outbound 포트 — 토큰 근사를 포트 뒤로 둡니다.

`aether_context.application` 이 바깥에 요구하는 계약입니다. 실제 구현(문자 ÷ 4
올림)은 `adapters/outbound/token_counter/char_approx.py` 입니다 — 토크나이저
의존을 들이지 않고(D-6), 어긋남은 과대 추정 방향으로 고정합니다(C-2).
"""

from __future__ import annotations

from typing import Protocol


class TokenCounter(Protocol):
    def count(self, text: str) -> int:
        """`text` 의 토큰 수 추정. 실제 토크나이저와 어긋날 수 있으나 그 방향은
        항상 과대 추정입니다(D-6, C-2)."""
        ...
