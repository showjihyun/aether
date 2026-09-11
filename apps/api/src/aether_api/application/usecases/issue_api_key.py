"""spec 0001 D-3 · 2.9 (H-3 설계 검토): `IssueApiKey` 포트의 구현.

표준 라이브러리와 `domain`·`application.ports` 만 import 합니다(AR-9).
"""

from __future__ import annotations

import secrets
from collections.abc import Callable

from aether_api.application.ports.inbound.issue_api_key import IssuedApiKey
from aether_api.application.ports.outbound.api_keys import ApiKeyStore
from aether_api.domain.api_key import generate_raw_key, hash_key


class IssueApiKeyUseCase:
    """`ApiKeyStore` 하나로 inbound 포트 `IssueApiKey` 를 구현합니다."""

    def __init__(
        self,
        store: ApiKeyStore,
        rand: Callable[[int], bytes] = secrets.token_bytes,
    ) -> None:
        self._store = store
        self._rand = rand

    def __call__(self, label: str) -> IssuedApiKey:
        raw = generate_raw_key(self._rand)
        key = self._store.create(label, hash_key(raw))
        return IssuedApiKey(raw_key=raw, key=key)
