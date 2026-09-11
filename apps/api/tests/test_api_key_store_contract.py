"""spec 0001 2.9 · 2.8 (H-3 설계 검토): `ApiKeyStore` 포트 계약 — fake 와 PostgreSQL 이 같은 케이스.

`postgres` 케이스는 `conftest.py` 의 `control_connection_factory`(`aether_control` 역할,
`alembic upgrade head` 로 마이그레이션된 세션 DB)를 그대로 `PostgresApiKeyStore` 의 연결
**팩토리**로 건넵니다 — 어댑터가 메서드마다 연결을 열고 커밋하고 닫으므로(H-3), 여기서
따로 열고 롤백할 필요가 없습니다. 대신 각 테스트는 매번 새 해시(`hash_key(generate_raw_key())`)
를 씁니다 — 커밋된 행이 세션 DB(컨테이너)에 그대로 남기 때문에 리터럴 해시를 재사용하면
테스트끼리 충돌합니다.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from uuid import uuid4

import psycopg
import pytest
from aether_api.application.ports.outbound.api_keys import ApiKeyStore
from aether_api.domain.api_key import generate_raw_key, hash_key
from fakes import FakeApiKeyStore


def _unique_hash() -> str:
    return hash_key(generate_raw_key())


@contextmanager
def _fake_store() -> Iterator[ApiKeyStore]:
    yield FakeApiKeyStore()


@contextmanager
def _postgres_store(
    control_connection_factory: Callable[[], psycopg.Connection],
) -> Iterator[ApiKeyStore]:
    from aether_api.adapters.outbound.db.api_keys import PostgresApiKeyStore

    yield PostgresApiKeyStore(control_connection_factory)


def _store_kinds() -> list[object]:
    return [
        pytest.param("fake", id="fake"),
        pytest.param("postgres", id="postgres", marks=pytest.mark.integration),
    ]


@contextmanager
def _make_store(kind: str, request: pytest.FixtureRequest) -> Iterator[ApiKeyStore]:
    if kind == "fake":
        with _fake_store() as store:
            yield store
        return
    factory = request.getfixturevalue("control_connection_factory")
    with _postgres_store(factory) as store:
        yield store


@pytest.mark.parametrize("store_kind", _store_kinds())
def test_create_then_find_by_hash_returns_same_key(
    store_kind: str, request: pytest.FixtureRequest
) -> None:
    key_hash = _unique_hash()
    with _make_store(store_kind, request) as store:
        created = store.create("ci", key_hash)

        found = store.find_by_hash(key_hash)

    assert found is not None
    assert found.id == created.id
    assert found.label == "ci"
    assert found.key_hash == key_hash
    assert found.revoked_at is None


@pytest.mark.parametrize("store_kind", _store_kinds())
def test_find_by_hash_returns_none_for_unregistered_hash(
    store_kind: str, request: pytest.FixtureRequest
) -> None:
    with _make_store(store_kind, request) as store:
        found = store.find_by_hash(_unique_hash())

    assert found is None


@pytest.mark.parametrize("store_kind", _store_kinds())
def test_revoke_sets_revoked_at_and_deactivates(
    store_kind: str, request: pytest.FixtureRequest
) -> None:
    key_hash = _unique_hash()
    with _make_store(store_kind, request) as store:
        created = store.create("ci", key_hash)

        store.revoke(created.id)

        found = store.find_by_hash(key_hash)

    assert found is not None
    assert found.revoked_at is not None
    assert found.is_active is False


@pytest.mark.parametrize("store_kind", _store_kinds())
def test_second_revoke_keeps_first_revoked_at(
    store_kind: str, request: pytest.FixtureRequest
) -> None:
    """spec 2.9 H-3: `revoke` 는 멱등 — 두 번째 호출은 첫 `revoked_at` 을 유지합니다.

    두 호출 사이에 짧게 잠들어(`time.sleep`) 시계가 반드시 움직이게 합니다 — 그렇지
    않으면 시계 해상도가 낮은 환경(Windows)에서 "덮어쓰기" 구현도 우연히 같은 값을
    반환해 이 테스트가 거짓으로 통과할 수 있습니다.
    """
    key_hash = _unique_hash()
    with _make_store(store_kind, request) as store:
        created = store.create("ci", key_hash)

        store.revoke(created.id)
        first_revoked_at = store.find_by_hash(key_hash)
        assert first_revoked_at is not None

        time.sleep(0.02)
        store.revoke(created.id)
        second_revoked_at = store.find_by_hash(key_hash)

    assert second_revoked_at is not None
    assert second_revoked_at.revoked_at == first_revoked_at.revoked_at


@pytest.mark.parametrize("store_kind", _store_kinds())
def test_revoke_unknown_id_raises_key_error(
    store_kind: str, request: pytest.FixtureRequest
) -> None:
    """spec 2.9 H-3: 없는 id 의 `revoke` 는 `KeyError`."""
    with _make_store(store_kind, request) as store:
        with pytest.raises(KeyError):
            store.revoke(uuid4())


@pytest.mark.parametrize("store_kind", _store_kinds())
def test_duplicate_key_hash_on_create_raises(
    store_kind: str, request: pytest.FixtureRequest
) -> None:
    key_hash = _unique_hash()
    with _make_store(store_kind, request) as store:
        store.create("first", key_hash)

        with pytest.raises(Exception):  # noqa: B017 -- unique 위반의 정확한 타입은 구현마다 다름
            store.create("second", key_hash)


@pytest.mark.integration
def test_postgres_does_not_persist_raw_key(
    control_connection_factory: Callable[[], psycopg.Connection],
) -> None:
    """PostgreSQL 쪽만: 테이블 열에 원문(raw)이 들어갈 자리가 없습니다(spec 2.9 저장 행)."""
    with _postgres_store(control_connection_factory) as store:
        store.create("ci", _unique_hash())

    conn = control_connection_factory()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT column_name FROM information_schema.columns
                WHERE table_schema = 'control' AND table_name = 'api_keys'
                """
            )
            columns = {row[0] for row in cur.fetchall()}
    finally:
        conn.close()

    assert columns == {"id", "label", "key_hash", "created_at", "revoked_at"}
