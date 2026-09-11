"""spec 0001 2.9: `ApiKeyStore` 의 dict 기반 fake — 컨테이너 없는 유스케이스 테스트용.

`calls` 는 어떤 메서드가 어떤 인자로 불렸는지 순서대로 기록합니다.
`test_authenticate.py` 가 이것으로 "형식 불량 키는 store 를 조회하지 않는다"(spec 2.9,
열거 공격 표면 축소)를 증명합니다. 테스트 지원 코드이며 제품 코드가 아닙니다.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from uuid import UUID, uuid4

from aether_api.domain.api_key import ApiKey


class FakeApiKeyStore:
    """`ApiKeyStore` 포트 계약의 인메모리 구현."""

    def __init__(self) -> None:
        self._by_id: dict[UUID, ApiKey] = {}
        self._id_by_hash: dict[str, UUID] = {}
        self.calls: list[tuple[str, str]] = []

    def find_by_hash(self, key_hash: str) -> ApiKey | None:
        self.calls.append(("find_by_hash", key_hash))
        key_id = self._id_by_hash.get(key_hash)
        if key_id is None:
            return None
        return self._by_id[key_id]

    def create(self, label: str, key_hash: str) -> ApiKey:
        self.calls.append(("create", key_hash))
        if key_hash in self._id_by_hash:
            raise ValueError(f"duplicate key_hash: {key_hash!r}")
        key = ApiKey(
            id=uuid4(),
            label=label,
            key_hash=key_hash,
            created_at=datetime.now(UTC),
            revoked_at=None,
        )
        self._by_id[key.id] = key
        self._id_by_hash[key_hash] = key.id
        return key

    def revoke(self, key_id: UUID) -> None:
        """멱등: 이미 폐기된 키는 `revoked_at` 을 그대로 둡니다. 없는 id 는 `KeyError`."""
        self.calls.append(("revoke", str(key_id)))
        existing = self._by_id[key_id]  # 없으면 KeyError — 포트 계약(spec 2.9 H-3)
        if existing.revoked_at is None:
            self._by_id[key_id] = replace(existing, revoked_at=datetime.now(UTC))

    # 테스트 준비 편의 — 포트 계약에는 없습니다.
    def seed(self, key: ApiKey) -> None:
        self._by_id[key.id] = key
        self._id_by_hash[key.key_hash] = key.id
