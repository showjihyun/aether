"""spec 0002 C-13, D-10 (P1-7): `ThreadedLeaseKeeper` — `LeaseKeeper` 포트의 프로덕션
구현. `RunStateStore.renew_lease` 를 주기(`ttl_seconds * interval_ratio`)마다 부르고,
`False`(또는 예외)를 돌려받으면 `LeaseStatus.lost` 를 참으로 남기고 스스로 멈춥니다.
`time.sleep` 을 쓰지 않습니다(`threading.Event.wait`) — `tests/arch/
test_no_sleep_in_tests.py` 대상.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID, uuid4

from aether_runtime.adapters.outbound.threaded_lease_keeper import ThreadedLeaseKeeper
from aether_runtime.domain.failure import FailureReason
from aether_runtime.domain.run import RunState, RunStatus

from tests.support.waiting import wait_until

_OWNER = "worker-a"


@dataclass
class _CountingRunStateStore:
    """`RunStateStore` 포트의 최소 stub — `renew_lease` 호출 횟수·인자·반환 값
    시퀀스만 통제합니다. 그 밖의 메서드는 이 테스트에서 부르지 않습니다."""

    renew_results: list[bool] = field(default_factory=lambda: [True] * 100)
    calls: list[tuple[UUID, str, float]] = field(default_factory=list)

    def load(self, run_id: UUID) -> RunState | None:
        raise NotImplementedError

    def save(self, state: RunState) -> None:
        raise NotImplementedError

    def acquire_lease(self, run_id: UUID, owner: str, ttl_seconds: float) -> bool:
        raise NotImplementedError

    def renew_lease(self, run_id: UUID, owner: str, ttl_seconds: float) -> bool:
        self.calls.append((run_id, owner, ttl_seconds))
        index = len(self.calls) - 1
        result = self.renew_results[index] if index < len(self.renew_results) else True
        return result

    def release(self, run_id: UUID, owner: str) -> None:
        raise NotImplementedError

    def status(self, run_id: UUID) -> RunStatus | None:
        raise NotImplementedError

    def set_status(
        self,
        run_id: UUID,
        status: RunStatus,
        *,
        failure_reason: FailureReason | None = None,
        trace_id: str | None = None,
        started_at: datetime | None = None,
        finished_at: datetime | None = None,
    ) -> None:
        raise NotImplementedError


def _lease_keeper_threads() -> list[threading.Thread]:
    return [t for t in threading.enumerate() if t.name.startswith("lease-keeper-")]


def test_renews_lease_periodically_while_kept() -> None:
    """spec 0002 C-13: `ttl_seconds * interval_ratio` 간격으로 `renew_lease` 가 최소
    두 번 이상 불립니다(`ttl_seconds=0.3, interval_ratio=1/3` → 간격 0.1초)."""
    store = _CountingRunStateStore()
    keeper = ThreadedLeaseKeeper(store, interval_ratio=1 / 3)
    run_id = uuid4()

    with keeper.keep(run_id, _OWNER, 0.3) as status:
        assert wait_until(lambda: len(store.calls) >= 2, timeout=2.0), (
            "renew_lease 가 충분히 여러 번 불리지 않았습니다"
        )
        assert status.lost is False

    assert all(call == (run_id, _OWNER, 0.3) for call in store.calls)


def test_context_exit_stops_the_background_thread() -> None:
    """spec 0002 C-13: `with` 블록을 벗어나면 갱신 스레드가 멈추고 `join` 됩니다 —
    컨텍스트 종료 뒤 `lease-keeper-*` 이름의 스레드가 살아 있지 않습니다."""
    store = _CountingRunStateStore()
    keeper = ThreadedLeaseKeeper(store, interval_ratio=1 / 3)
    run_id = uuid4()

    with keeper.keep(run_id, _OWNER, 0.3):
        assert wait_until(lambda: len(store.calls) >= 1, timeout=2.0)
        assert len(_lease_keeper_threads()) == 1

    assert _lease_keeper_threads() == []


def test_renew_lease_returning_false_marks_lost_and_stops_renewing() -> None:
    """spec 0002 C-13: 갱신 실패(`False`) → `lost=True`, 이후 `renew_lease` 호출이
    더 늘지 않습니다(스레드가 스스로 멈춤)."""
    store = _CountingRunStateStore(renew_results=[True, False, True, True, True])
    keeper = ThreadedLeaseKeeper(store, interval_ratio=1 / 3)
    run_id = uuid4()

    with keeper.keep(run_id, _OWNER, 0.3) as status:
        assert wait_until(lambda: status.lost is True, timeout=2.0), "lost 가 되지 않았습니다"
        calls_at_loss = len(store.calls)
        assert calls_at_loss == 2
        # 짧게 기다려도 더는 늘지 않습니다(스레드가 스스로 멈췄습니다) — 이 부정 확인은
        # 참이 될 것을 기다리는 게 아니라 "늘지 않았다" 를 보이는 것이므로 반환값이
        # `False` 인 것 자체가 통과 조건입니다.
        assert not wait_until(lambda: len(store.calls) > calls_at_loss, timeout=0.3)

    assert len(store.calls) == calls_at_loss


def test_exception_from_renew_lease_marks_lost() -> None:
    """spec 0002 C-13: DB 단절(예외)도 갱신 실패와 같이 `lost=True` 로 취급합니다."""

    class _RaisingStore(_CountingRunStateStore):
        def renew_lease(self, run_id: UUID, owner: str, ttl_seconds: float) -> bool:
            self.calls.append((run_id, owner, ttl_seconds))
            raise RuntimeError("connection lost")

    store = _RaisingStore()
    keeper = ThreadedLeaseKeeper(store, interval_ratio=1 / 3)
    run_id = uuid4()

    with keeper.keep(run_id, _OWNER, 0.3) as status:
        assert wait_until(lambda: status.lost is True, timeout=2.0)
