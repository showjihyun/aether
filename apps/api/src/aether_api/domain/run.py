"""spec 0002 2.1, 2.2, 2.4, D-9, D-11: Control Plane 의 `Run` 투영 값 객체와 예외.

`RunView` 는 `control.runs` 의 선언·투영 열을 그대로 담습니다(spec 0001 D-11 —
`GET /runs/{id}` 는 이 투영만 읽습니다). `status`·`failure_reason` 은
`aether_runtime.domain` 의 타입을 그대로 씁니다 — api 는 `aether_runtime.domain` 만
import 할 수 있고(AR-7 확장) 그 타입을 복제하지 않습니다. `Agent`(정의)와
`Agent Version`(그 정의의 불변 스냅숏)과 `Run`(실행)을 혼용하지 않습니다
([../../../../../docs/domain.md](../../../../../docs/domain.md) 1절).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from aether_runtime.domain.failure import FailureReason
from aether_runtime.domain.run import RunStatus


@dataclass(frozen=True)
class RunView:
    """`control.runs` 한 행의 선언·투영 열 — `GET /runs/{id}` 의 정본(spec 0001 D-11)."""

    run_id: UUID
    agent_id: UUID
    agent_version: int
    status: RunStatus
    requested_at: datetime
    requested_by: UUID
    started_at: datetime | None
    finished_at: datetime | None
    failure_reason: FailureReason | None
    trace_id: str | None
    cancel_requested_at: datetime | None


class RunNotFound(Exception):
    """주어진 `run_id` 의 Run 이 없습니다(spec 2.2 `404 run_not_found`)."""
