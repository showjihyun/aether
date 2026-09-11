"""spec 0001 R-9 · D-3 · 2.9 (H-3 설계 검토): `Authenticate` 포트의 구현.

표준 라이브러리와 `domain`·`application.ports` 만 import 합니다(AR-9). 실패 사유는
`Unauthenticated` 의 인자로만 전달됩니다 — 호출부(HTTP 어댑터)가 로그에 그 사유만
남기고, 키 원문·조각은 어디에도 남기지 않습니다.

검사 순서(spec 2.9 조회 행, H-3): 형식(`is_well_formed`)을 **먼저** 봅니다 — 형식이
불량이면 `store` 를 조회하지 않아 DB 를 때리는 열거 공격 표면이 줄고, 비ASCII 입력이
`hash_key` 의 `str.encode("ascii")` 에서 `UnicodeEncodeError` 를 내는 일도 없습니다.
"""

from __future__ import annotations

import hmac

from aether_api.application.ports.outbound.api_keys import ApiKeyStore
from aether_api.domain.api_key import Principal, Unauthenticated, hash_key, is_well_formed


class AuthenticateUseCase:
    """`ApiKeyStore` 하나로 inbound 포트 `Authenticate` 를 구현합니다."""

    def __init__(self, store: ApiKeyStore) -> None:
        self._store = store

    def __call__(self, raw_key: str | None) -> Principal:
        if not raw_key:
            raise Unauthenticated("missing")
        if not is_well_formed(raw_key):
            raise Unauthenticated("malformed")

        digest = hash_key(raw_key)
        key = self._store.find_by_hash(digest)
        if key is None:
            raise Unauthenticated("unregistered")
        if not hmac.compare_digest(key.key_hash, digest):
            raise Unauthenticated("hash_mismatch")
        if not key.is_active:
            raise Unauthenticated("revoked")

        return Principal(key_id=key.id, label=key.label)
