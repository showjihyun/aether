"""spec 0002 2.4, 2.18, D-2: `RunStatusMessage` — `aether:runs:status` 로 들어오는
투영 통지의 api 쪽 값 객체.

`aether_runtime.application.ports.outbound.status_notifier.StatusMessage` 와 필드가
같지만 그것을 import 하지 않습니다 — `aether_runtime.application` 은 api 에 금지된
모듈입니다(AR-7 확장, `aether_runtime.domain` 만 허용). 스트림 계약(spec 2.18)이
정본이고, worker(`aether_runtime`)와 api(`aether_api`) 양쪽이 그것을 각자 구현합니다
— 서로의 코드를 import 하지 않습니다(AR-7).
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from aether_runtime.domain.failure import FailureReason
from aether_runtime.domain.run import RunStatus
from pydantic import BaseModel


class RunStatusMessage(BaseModel):
    """`aether:runs:status` 필드(2.18) — `StatusConsumer` 가 파싱한 값."""

    run_id: UUID
    seq: int
    status: RunStatus
    at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    failure_reason: FailureReason | None = None
    trace_id: str | None = None
