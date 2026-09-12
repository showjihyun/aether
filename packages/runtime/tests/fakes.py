"""spec 0002 2.16, R-11, 2.4, D-10: `FakeClock`·`FakeRunStateStore` — 컨테이너 없는 테스트용.

`FakeClock` 은 `Clock` 포트의 인메모리 구현입니다(spec 0002 R-4, R-11) — `sleep` 은
실제로 기다리지 않고 `advance()` 와 같은 일을 해 시계만 전진시킵니다. 테스트는 이
`advance()` 로 시간을 직접 통제해 lease 만료 같은 시간 의존 동작을 결정적으로
재현합니다.

`FakeRunStateStore` 는 `RunStateStore` 포트의 인메모리 구현입니다. `backend` 를
외부에서 공유하면(`FakeRunStateStore.new_backend()`) 서로 다른 `FakeRunStateStore`
인스턴스가 같은 저장소를 보게 되어, PostgreSQL 어댑터가 연결마다 새로 열려도 같은
DB 를 보는 것과 같은 모양으로 "새 store 인스턴스가 같은 RunState 를 load" 계약을
검증할 수 있습니다(mvp-backlog P1-2b 완료 판정).

테스트 지원 코드이며 제품 코드가 아닙니다.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from uuid import UUID

from aether_runtime.domain.failure import FailureReason
from aether_runtime.domain.run import RunState, RunStatus


class FakeClock:
    """`Clock` 포트의 결정적 구현(spec 0002 R-11) — `sleep` 은 시계만 전진시킵니다."""

    def __init__(self, start: datetime | None = None) -> None:
        self._now = start if start is not None else datetime(2026, 1, 1, tzinfo=UTC)
        self._monotonic = 0.0

    def now(self) -> datetime:
        return self._now

    def monotonic(self) -> float:
        return self._monotonic

    def sleep(self, seconds: float) -> None:
        self.advance(seconds)

    def advance(self, seconds: float) -> None:
        """실제로 기다리지 않고 시계를 `seconds` 만큼 전진시킵니다."""
        self._now = self._now + timedelta(seconds=seconds)
        self._monotonic += seconds


@dataclass
class _Backend:
    """`FakeRunStateStore` 여러 인스턴스가 공유할 수 있는 저장소 본체."""

    states: dict[UUID, RunState] = field(default_factory=dict)
    status: dict[UUID, RunStatus] = field(default_factory=dict)
    failure_reason: dict[UUID, FailureReason | None] = field(default_factory=dict)
    trace_id: dict[UUID, str | None] = field(default_factory=dict)
    lease_owner: dict[UUID, str | None] = field(default_factory=dict)
    lease_until: dict[UUID, datetime | None] = field(default_factory=dict)


class FakeRunStateStore:
    """`RunStateStore` 포트의 인메모리 구현(spec 0002 2.1, 2.4, 2.10, D-10)."""

    def __init__(self, clock: FakeClock, *, backend: _Backend | None = None) -> None:
        self._clock = clock
        self._backend = backend if backend is not None else _Backend()

    @staticmethod
    def new_backend() -> _Backend:
        """여러 `FakeRunStateStore` 인스턴스가 공유할 빈 저장소를 만듭니다."""
        return _Backend()

    def load(self, run_id: UUID) -> RunState | None:
        state = self._backend.states.get(run_id)
        return state.model_copy(deep=True) if state is not None else None

    def save(self, state: RunState) -> None:
        self._backend.states[state.run_id] = state.model_copy(deep=True)

    def _ensure_execution_row(self, run_id: UUID) -> None:
        if run_id not in self._backend.status:
            self._backend.status[run_id] = RunStatus.QUEUED
            self._backend.failure_reason[run_id] = None
            self._backend.trace_id[run_id] = None
            self._backend.lease_owner[run_id] = None
            self._backend.lease_until[run_id] = None

    def acquire_lease(self, run_id: UUID, owner: str, ttl_seconds: float) -> bool:
        self._ensure_execution_row(run_id)
        until = self._backend.lease_until.get(run_id)
        now = self._clock.now()
        if until is not None and until >= now:
            return False
        self._backend.lease_owner[run_id] = owner
        self._backend.lease_until[run_id] = now + timedelta(seconds=ttl_seconds)
        return True

    def renew_lease(self, run_id: UUID, owner: str, ttl_seconds: float) -> bool:
        if self._backend.lease_owner.get(run_id) != owner:
            return False
        self._backend.lease_until[run_id] = self._clock.now() + timedelta(seconds=ttl_seconds)
        return True

    def release(self, run_id: UUID, owner: str) -> None:
        if self._backend.lease_owner.get(run_id) == owner:
            self._backend.lease_owner[run_id] = None
            self._backend.lease_until[run_id] = None

    def status(self, run_id: UUID) -> RunStatus | None:
        return self._backend.status.get(run_id)

    def set_status(
        self,
        run_id: UUID,
        status: RunStatus,
        *,
        failure_reason: FailureReason | None = None,
        trace_id: str | None = None,
    ) -> None:
        self._ensure_execution_row(run_id)
        self._backend.status[run_id] = status
        if failure_reason is not None:
            self._backend.failure_reason[run_id] = failure_reason
        if trace_id is not None:
            self._backend.trace_id[run_id] = trace_id
