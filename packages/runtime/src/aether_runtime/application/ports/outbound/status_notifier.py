"""spec 0002 2.1, 2.4, 2.18: `StatusMessage`·`StatusNotifier` — `aether:runs:status` 로
가는 투영 알림(D-2). `seq` 는 대응하는 `run.status` Run 이벤트의 `seq` 와 같은
수열입니다(2.4 투영 문단).
"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol
from uuid import UUID

from pydantic import BaseModel

from aether_runtime.domain.failure import FailureReason
from aether_runtime.domain.run import RunStatus


class StatusMessage(BaseModel):
    """`aether:runs:status` 필드(2.18)."""

    run_id: UUID
    seq: int
    status: RunStatus
    at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    failure_reason: FailureReason | None = None
    trace_id: str | None = None


class StatusNotifier(Protocol):
    def notify(self, message: StatusMessage) -> None: ...
