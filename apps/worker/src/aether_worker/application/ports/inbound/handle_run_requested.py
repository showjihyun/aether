"""spec 0002 2.1, 2.4, 2.18 (P1-5a): `HandleRunRequested` — worker 의 소비자
(`adapters/inbound/stream`)가 `aether:runs:requested` 에서 받은 메시지마다 부르는
inbound 포트. `HandleOutcome.ack` 이 소비자가 `XACK` 할지를 정합니다(D-10).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from aether_runtime.domain.run import RunStatus


@dataclass(frozen=True)
class RequestedMessage:
    """`aether:runs:requested` 한 항목을 파싱한 값(spec 2.18)."""

    message_id: str
    run_id: UUID
    agent_version_id: UUID
    traceparent: str | None


@dataclass(frozen=True)
class HandleOutcome:
    """`ack=True` 면 소비자가 `XACK` 합니다. `status` 는 실행이 끝난 경우의 최종
    `RunStatus`(로그·관측용 — 소비자는 이 값으로 분기하지 않습니다)."""

    ack: bool
    status: RunStatus | None


class HandleRunRequested(Protocol):
    def __call__(self, message: RequestedMessage) -> HandleOutcome: ...
