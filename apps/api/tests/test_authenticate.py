"""spec 0001 R-9 · D-3 · 2.9 (H-3 설계 검토): `Authenticate` 유스케이스, fake `ApiKeyStore` 로.

`AuthenticateUseCase(store: ApiKeyStore)` 가 inbound 포트 `Authenticate`
(`__call__(self, raw_key: str | None) -> Principal`)를 구현합니다.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from aether_api.application.usecases.authenticate import AuthenticateUseCase
from aether_api.domain.api_key import ApiKey, Unauthenticated, generate_raw_key, hash_key

from apps.api.tests.fakes import FakeApiKeyStore


def _seed_active_key(store: FakeApiKeyStore, *, raw: str, label: str = "ci") -> ApiKey:
    key = ApiKey(
        id=uuid4(),
        label=label,
        key_hash=hash_key(raw),
        created_at=datetime.now(UTC),
        revoked_at=None,
    )
    store.seed(key)
    return key


def test_valid_key_returns_matching_principal() -> None:
    store = FakeApiKeyStore()
    raw = generate_raw_key(lambda n: b"\x01" * n)
    seeded = _seed_active_key(store, raw=raw, label="ops-bot")

    principal = AuthenticateUseCase(store)(raw)

    assert principal.key_id == seeded.id
    assert principal.label == "ops-bot"


def test_missing_key_is_unauthenticated() -> None:
    store = FakeApiKeyStore()

    with pytest.raises(Unauthenticated):
        AuthenticateUseCase(store)(None)


def test_empty_key_is_unauthenticated() -> None:
    store = FakeApiKeyStore()

    with pytest.raises(Unauthenticated):
        AuthenticateUseCase(store)("")


def test_malformed_key_is_rejected_without_querying_store() -> None:
    """형식 불량은 store 를 조회하지 않습니다 — DB 를 때리는 열거 공격 표면 축소(spec 2.9)."""
    store = FakeApiKeyStore()

    with pytest.raises(Unauthenticated):
        AuthenticateUseCase(store)("not-a-valid-key")

    assert store.calls == []


def test_non_ascii_malformed_key_is_rejected_without_encoding_error() -> None:
    """spec 2.9 H-3: 비ASCII 불량 키는 `is_well_formed` 가 `hash_key` 보다 먼저 거부합니다.

    형식 검사를 건너뛰고 곧장 `hash_key`(`str.encode("ascii")`)를 호출했다면 이 입력은
    `UnicodeEncodeError` 를 냈을 것입니다 — 그 예외가 아니라 `Unauthenticated` 여야 합니다.
    """
    store = FakeApiKeyStore()
    bad = "aeth_" + ("é" * 43)

    with pytest.raises(Unauthenticated):
        AuthenticateUseCase(store)(bad)

    assert store.calls == []


def test_unregistered_key_is_unauthenticated() -> None:
    store = FakeApiKeyStore()
    raw = generate_raw_key(lambda n: b"\x02" * n)

    with pytest.raises(Unauthenticated):
        AuthenticateUseCase(store)(raw)

    assert store.calls == [("find_by_hash", hash_key(raw))]


def test_revoked_key_is_unauthenticated() -> None:
    store = FakeApiKeyStore()
    raw = generate_raw_key(lambda n: b"\x03" * n)
    key = _seed_active_key(store, raw=raw)
    store.revoke(key.id)
    store.calls.clear()

    with pytest.raises(Unauthenticated):
        AuthenticateUseCase(store)(raw)


def test_store_is_queried_by_sha256_hex_not_raw_text() -> None:
    store = FakeApiKeyStore()
    raw = generate_raw_key(lambda n: b"\x04" * n)
    _seed_active_key(store, raw=raw)

    AuthenticateUseCase(store)(raw)

    queried_hashes = [value for method, value in store.calls if method == "find_by_hash"]
    assert queried_hashes == [hash_key(raw)]
    assert raw not in queried_hashes


def test_uses_constant_time_comparison(monkeypatch: pytest.MonkeyPatch) -> None:
    """spec 2.9 조회 행: 비교는 `hmac.compare_digest`.

    `hmac` 는 표준 라이브러리 싱글턴 모듈이므로, 여기서 직접 `import hmac` 해 그
    전역 함수를 감시해도 `authenticate.py` 안의 `import hmac` 이 가리키는 것과
    같은 모듈 객체입니다 — 내부 모듈의 네임스페이스를 넘겨보지 않아도 됩니다
    (mypy strict 의 `implicit_reexport=False` 와도 충돌하지 않습니다).
    """
    import hmac

    store = FakeApiKeyStore()
    raw = generate_raw_key(lambda n: b"\x05" * n)
    _seed_active_key(store, raw=raw)

    calls: list[tuple[str, str]] = []
    original = hmac.compare_digest

    def _spy(a: str, b: str) -> bool:
        calls.append((a, b))
        return bool(original(a, b))

    monkeypatch.setattr(hmac, "compare_digest", _spy)

    AuthenticateUseCase(store)(raw)

    assert calls, "hmac.compare_digest 가 호출되지 않았습니다"
