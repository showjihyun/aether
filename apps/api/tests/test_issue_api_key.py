"""spec 0001 D-3 · 2.9 (H-3 설계 검토): `IssueApiKey` 유스케이스, fake `ApiKeyStore` + 주입 난수로.

`IssueApiKeyUseCase(store: ApiKeyStore, rand: Callable[[int], bytes] = secrets.token_bytes)`
가 inbound 포트 `IssueApiKey`(`__call__(self, label: str) -> IssuedApiKey`)를 구현합니다.
`rand` 는 `domain.api_key.generate_raw_key` 에 그대로 전달되어 테스트 결정성을 줍니다.
"""

from __future__ import annotations

from collections.abc import Callable

import pytest
from aether_api.application.usecases.issue_api_key import IssueApiKeyUseCase
from aether_api.domain.api_key import hash_key, is_well_formed
from fakes import FakeApiKeyStore


def _fixed_rand(byte: bytes) -> Callable[[int], bytes]:
    def _rand(n: int) -> bytes:
        return byte * n

    return _rand


def test_issued_raw_key_is_well_formed() -> None:
    store = FakeApiKeyStore()
    issue = IssueApiKeyUseCase(store, rand=_fixed_rand(b"\xaa"))

    issued = issue("ci-runner")

    assert is_well_formed(issued.raw_key)


def test_stored_hash_matches_issued_raw_key() -> None:
    store = FakeApiKeyStore()
    issue = IssueApiKeyUseCase(store, rand=_fixed_rand(b"\xbb"))

    issued = issue("ci-runner")

    assert issued.key.key_hash == hash_key(issued.raw_key)


def test_label_is_stored() -> None:
    store = FakeApiKeyStore()
    issue = IssueApiKeyUseCase(store, rand=_fixed_rand(b"\xcc"))

    issued = issue("release-bot")

    assert issued.key.label == "release-bot"


def test_repeated_randomness_fails_on_duplicate_hash() -> None:
    """같은 난수를 두 번 주입하면 두 번째 `create` 가 store 계약(unique)에 의해 실패합니다."""
    store = FakeApiKeyStore()
    issue = IssueApiKeyUseCase(store, rand=_fixed_rand(b"\xdd"))

    issue("first")

    with pytest.raises(ValueError):  # FakeApiKeyStore.create 의 unique 위반
        issue("second")
