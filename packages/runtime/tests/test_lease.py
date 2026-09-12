"""spec 0002 D-10, R-15: 실행 권한 lease — 유효 lease 는 두 번째 획득을 막고, 만료
뒤에는 다시 잡을 수 있습니다. `FakeClock.advance()` 로 만료를 결정적으로 재현합니다
(`time.sleep` 없음, R-11).
"""

from __future__ import annotations

from uuid import uuid4

from packages.runtime.tests.fakes import FakeClock, FakeRunStateStore


def test_acquire_lease_succeeds_for_a_fresh_run() -> None:
    store = FakeRunStateStore(FakeClock())
    run_id = uuid4()

    acquired = store.acquire_lease(run_id, owner="worker-a", ttl_seconds=60)

    assert acquired is True


def test_second_acquire_lease_fails_while_first_is_still_valid() -> None:
    store = FakeRunStateStore(FakeClock())
    run_id = uuid4()
    assert store.acquire_lease(run_id, owner="worker-a", ttl_seconds=60) is True

    second = store.acquire_lease(run_id, owner="worker-b", ttl_seconds=60)

    assert second is False


def test_acquire_lease_succeeds_again_after_expiry() -> None:
    clock = FakeClock()
    store = FakeRunStateStore(clock)
    run_id = uuid4()
    assert store.acquire_lease(run_id, owner="worker-a", ttl_seconds=60) is True

    clock.advance(61)
    acquired = store.acquire_lease(run_id, owner="worker-b", ttl_seconds=60)

    assert acquired is True


def test_acquire_lease_still_fails_one_second_before_expiry() -> None:
    clock = FakeClock()
    store = FakeRunStateStore(clock)
    run_id = uuid4()
    assert store.acquire_lease(run_id, owner="worker-a", ttl_seconds=60) is True

    clock.advance(59)
    acquired = store.acquire_lease(run_id, owner="worker-b", ttl_seconds=60)

    assert acquired is False


def test_renew_lease_succeeds_for_the_current_owner_and_extends_it() -> None:
    clock = FakeClock()
    store = FakeRunStateStore(clock)
    run_id = uuid4()
    assert store.acquire_lease(run_id, owner="worker-a", ttl_seconds=10) is True

    clock.advance(9)
    renewed = store.renew_lease(run_id, owner="worker-a", ttl_seconds=10)
    assert renewed is True

    # 갱신되지 않았다면 최초 10초 lease 는 이미 9초 지난 시점이라 1초 뒤 만료였을 것.
    clock.advance(9)
    assert store.acquire_lease(run_id, owner="worker-b", ttl_seconds=10) is False


def test_renew_lease_fails_for_a_different_owner() -> None:
    store = FakeRunStateStore(FakeClock())
    run_id = uuid4()
    assert store.acquire_lease(run_id, owner="worker-a", ttl_seconds=60) is True

    renewed = store.renew_lease(run_id, owner="worker-b", ttl_seconds=60)

    assert renewed is False


def test_release_then_acquire_by_new_owner_succeeds_immediately() -> None:
    store = FakeRunStateStore(FakeClock())
    run_id = uuid4()
    assert store.acquire_lease(run_id, owner="worker-a", ttl_seconds=60) is True

    store.release(run_id, owner="worker-a")
    acquired = store.acquire_lease(run_id, owner="worker-b", ttl_seconds=60)

    assert acquired is True


def test_release_by_non_owner_is_a_no_op() -> None:
    store = FakeRunStateStore(FakeClock())
    run_id = uuid4()
    assert store.acquire_lease(run_id, owner="worker-a", ttl_seconds=60) is True

    store.release(run_id, owner="worker-b")
    still_held = store.acquire_lease(run_id, owner="worker-c", ttl_seconds=60)

    assert still_held is False
