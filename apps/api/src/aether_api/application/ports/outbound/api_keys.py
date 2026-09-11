"""spec 0001 2.9 · 2.8: `control.api_keys` 에 대한 outbound 포트.

`ApiKeyStore` 의 fake 구현과 PostgreSQL 구현(`adapters/outbound/db/api_keys.py`, 2단계)은
같은 포트 계약 테스트(`tests/test_api_key_store_contract.py`)를 통과해야 합니다. 이
포트는 원문 키를 전혀 다루지 않습니다 — 유스케이스가 해시한 값만 오갑니다.
"""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from aether_api.domain.api_key import ApiKey


class ApiKeyStore(Protocol):
    """`control.api_keys` 저장소 계약."""

    def find_by_hash(self, key_hash: str) -> ApiKey | None:
        """`key_hash` 와 정확히 일치하는 키를 반환하거나, 없으면 `None`."""
        ...

    def create(self, label: str, key_hash: str) -> ApiKey:
        """새 행을 만들어 반환합니다. `key_hash` 중복이면 예외를 던집니다(unique 제약)."""
        ...

    def revoke(self, key_id: UUID) -> None:
        """`revoked_at` 을 지금 시각으로 설정합니다."""
        ...
