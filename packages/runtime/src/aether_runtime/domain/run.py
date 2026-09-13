"""spec 0002 2.1, 2.4: `RunStatus`, 전이표, `RunState`, `IllegalTransition`, `LeaseHeld`.

`docs/domain.md` 1절: `State`(여기서는 `RunState`)는 `Run` 의 진행 상태이지 `Memory` 가
아닙니다 — 재시작 후 이어붙일 수 있어야 합니다(재개는 P1-4 의 `ExecuteRun` 이 완결).
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from aether_runtime.domain.failure import FailureReason
from aether_runtime.domain.task import Task


class RunStatus(StrEnum):
    """`data.run_execution_status`(마이그레이션 0001)와 같은 값."""

    QUEUED = "queued"
    RUNNING = "running"
    WAITING = "waiting"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"


_TERMINAL_STATUSES: frozenset[RunStatus] = frozenset(
    {RunStatus.SUCCEEDED, RunStatus.FAILED, RunStatus.CANCELLED, RunStatus.TIMED_OUT}
)

# spec 0002 2.4 의 전이표. `(없음) -> queued` 는 api 의 INSERT 이지 이 함수의 전이가
# 아닙니다 — 여기는 이미 존재하는 실행 상태 사이의 전이만 다룹니다.
_ALLOWED_TRANSITIONS: dict[RunStatus, frozenset[RunStatus]] = {
    RunStatus.QUEUED: frozenset({RunStatus.RUNNING, RunStatus.CANCELLED}),
    RunStatus.RUNNING: frozenset(
        {
            RunStatus.WAITING,
            RunStatus.SUCCEEDED,
            RunStatus.FAILED,
            RunStatus.CANCELLED,
            RunStatus.TIMED_OUT,
        }
    ),
    RunStatus.WAITING: frozenset(
        {
            RunStatus.RUNNING,
            RunStatus.SUCCEEDED,
            RunStatus.FAILED,
            RunStatus.CANCELLED,
            RunStatus.TIMED_OUT,
        }
    ),
    RunStatus.SUCCEEDED: frozenset(),
    RunStatus.FAILED: frozenset(),
    RunStatus.CANCELLED: frozenset(),
    RunStatus.TIMED_OUT: frozenset(),
}


class IllegalTransition(Exception):
    """허용되지 않은 전이 — 종결 상태에서 나가는 전이를 포함합니다."""

    def __init__(self, current: RunStatus, target: RunStatus) -> None:
        super().__init__(f"illegal transition: {current.value} -> {target.value}")
        self.current = current
        self.target = target


class LeaseHeld(Exception):
    """다른 worker 가 이 Run 의 실행 권한(lease)을 이미 쥐고 있습니다(spec 0002 D-10, R-15)."""

    def __init__(self, run_id: UUID) -> None:
        super().__init__(f"lease already held for run {run_id}")
        self.run_id = run_id


def is_terminal(status: RunStatus) -> bool:
    return status in _TERMINAL_STATUSES


def transition(current: RunStatus, target: RunStatus) -> RunStatus:
    """`current` 에서 `target` 으로의 전이가 spec 2.4 표에 있으면 `target` 을, 아니면
    `IllegalTransition` 을 냅니다."""
    if target not in _ALLOWED_TRANSITIONS[current]:
        raise IllegalTransition(current, target)
    return target


class Message(BaseModel):
    """모델에 오가는 메시지 하나. `tool_call_id` 는 `role == "tool"` 일 때만 채워집니다."""

    role: Literal["system", "user", "assistant", "tool"]
    content: str
    tool_call_id: str | None = None


class RunState(BaseModel):
    """Run 의 재개 가능한 진행 상태 — `data.run_states.state` 에 그대로 jsonb 로 저장됩니다.

    `last_seq` 는 이 Run 이 마지막으로 발행한 이벤트의 `seq`(2.7 — Run 안에서 1 부터
    단조 증가)이고, 음수가 될 수 없습니다.

    `failure_reason`·`started_at`·`finished_at` 은 종결 시의 재발행(R-16)이 이 스냅숏
    하나만으로 `run.status`·`run.finished` 를 다시 만들 수 있도록 P1-4 의 `ExecuteRun`
    이 여기에 함께 저장합니다 — `RunStateStore` 포트에는 이 값을 따로 읽는 문이 없으므로
    (2.1 이 정한 `load`/`save`/`status` 뿐), 재개 가능한 `State` 자신이 정본입니다.
    """

    run_id: UUID
    messages: list[Message] = Field(default_factory=list)
    step: int = Field(default=0, ge=0)
    tasks: list[Task] = Field(default_factory=list)
    last_seq: int = Field(default=0, ge=0)
    status: RunStatus
    failure_reason: FailureReason | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
