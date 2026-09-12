"""spec 0002 2.1, 2.4, 2.10, D-10: `RunStateStore` — `data.run_executions`(상태·lease)와
`data.run_states`(스냅숏) 계약.

시각은 전부 **DB 시계**(`now()`) 기준입니다 — 어댑터는 `Clock` 포트를 받지 않습니다
(worker 의 타임아웃·백오프만 `Clock` 을 통해 결정적으로 테스트되고, lease 만료는
저장소가 소유한 시계 하나로 여러 worker 사이의 경합을 판정합니다).
"""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from aether_runtime.domain.failure import FailureReason
from aether_runtime.domain.run import RunState, RunStatus


class RunStateStore(Protocol):
    def load(self, run_id: UUID) -> RunState | None: ...

    def save(self, state: RunState) -> None: ...

    def acquire_lease(self, run_id: UUID, owner: str, ttl_seconds: float) -> bool:
        """행이 없으면 `queued` 실행 행을 만들고 잡습니다. `lease_until` 이 비었거나
        지났을 때만 성공합니다(조건부 UPDATE, 원자적)."""
        ...

    def renew_lease(self, run_id: UUID, owner: str, ttl_seconds: float) -> bool: ...

    def release(self, run_id: UUID, owner: str) -> None: ...

    def status(self, run_id: UUID) -> RunStatus | None: ...

    def set_status(
        self,
        run_id: UUID,
        status: RunStatus,
        *,
        failure_reason: FailureReason | None = None,
        trace_id: str | None = None,
    ) -> None: ...
