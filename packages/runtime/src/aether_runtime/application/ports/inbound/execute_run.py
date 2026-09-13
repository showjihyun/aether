"""spec 0002 2.1: `ExecuteRun` — worker 가 부르는 유일한 문.

다른 worker 가 이 Run 의 lease 를 이미 쥐고 있으면 `LeaseHeld` 를 냅니다(D-10, R-15) —
호출자(worker)는 그 예외를 보고 메시지를 ack 하지 않습니다.
"""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from aether_runtime.domain.run import RunStatus


class ExecuteRun(Protocol):
    def __call__(self, run_id: UUID) -> RunStatus: ...
