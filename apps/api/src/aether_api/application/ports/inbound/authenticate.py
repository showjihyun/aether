"""spec 0001 R-9 · D-3 · 2.9: 요청의 API 키를 검증해 `Principal` 을 돌려주는 inbound 포트.

HTTP 의존성(`adapters/inbound/http/auth.py`)과 CLI 는 구현이 아니라 이 포트 타입만
봅니다(AR-12). 실패는 예외 `Unauthenticated` 로만 표현합니다 — `None` 을 반환해
"인증 안 됨"을 표현하지 않는 것은, 호출부가 실패를 무시하기 쉬워지는 것을 막기
위해서입니다.
"""

from __future__ import annotations

from typing import Protocol

from aether_api.domain.api_key import Principal


class Authenticate(Protocol):
    """`raw_key` 가 유효한 활성 키의 원문이면 그 키의 `Principal` 을 반환합니다.

    `raw_key` 가 `None`/빈 문자열/형식 불량/미등록/폐기 중 하나면 `Unauthenticated` 를
    던집니다(spec 2.9 조회 행).
    """

    def __call__(self, raw_key: str | None) -> Principal: ...
