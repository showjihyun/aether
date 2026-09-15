"""spec 0002 C-13, D-10 (P1-7): `ThreadedLeaseKeeper` — `LeaseKeeper` 포트의
프로덕션 구현. `time.sleep` 을 쓰지 않습니다(`threading.Event.wait` 로 폴링, R-11 과
같은 규율을 프로덕션 코드에도 적용).

`keep(...)` 에 들어가면 데몬 스레드가 `ttl_seconds * interval_ratio` 간격으로
`RunStateStore.renew_lease` 를 부릅니다. 갱신이 `False` 를 돌려주거나(다른 worker가
이미 가져갔거나 lease 행이 사라짐) 예외를 내면(DB 단절) `LeaseStatus.lost` 를 참으로
남기고 스레드는 스스로 멈춥니다 — 더 이상 갱신해도 의미가 없기 때문입니다.
컨텍스트를 벗어나면 스레드를 멈추고 `join` 합니다.
"""

from __future__ import annotations

import threading
from collections.abc import Iterator
from contextlib import contextmanager
from uuid import UUID

from aether_runtime.application.ports.outbound.run_state_store import RunStateStore

_DEFAULT_INTERVAL_RATIO = 1 / 3


class _MutableLeaseStatus:
    """`LeaseStatus` 포트 구현 — 갱신 스레드가 쓰고, 유스케이스가 읽습니다."""

    def __init__(self) -> None:
        self._lost = False

    @property
    def lost(self) -> bool:
        return self._lost

    def _mark_lost(self) -> None:
        self._lost = True


class ThreadedLeaseKeeper:
    """`LeaseKeeper` 포트의 프로덕션 구현(spec 0002 C-13)."""

    def __init__(
        self, store: RunStateStore, *, interval_ratio: float = _DEFAULT_INTERVAL_RATIO
    ) -> None:
        self._store = store
        self._interval_ratio = interval_ratio

    @contextmanager
    def keep(self, run_id: UUID, owner: str, ttl_seconds: float) -> Iterator[_MutableLeaseStatus]:
        status = _MutableLeaseStatus()
        stop = threading.Event()
        interval = ttl_seconds * self._interval_ratio

        def _renew_loop() -> None:
            while not stop.wait(interval):
                try:
                    renewed = self._store.renew_lease(run_id, owner, ttl_seconds)
                except Exception:  # noqa: BLE001 -- DB 단절 등, 원인과 무관하게 lost 로 취급
                    status._mark_lost()
                    return
                if not renewed:
                    status._mark_lost()
                    return

        thread = threading.Thread(target=_renew_loop, name=f"lease-keeper-{run_id}", daemon=True)
        thread.start()
        try:
            yield status
        finally:
            stop.set()
            thread.join()
