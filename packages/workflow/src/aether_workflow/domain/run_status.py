"""spec 0005 2.3, D-1, D-2: Workflow Run 상태와 전이표.

Agent Run 의 `data.run_execution_status` 와 별도 enum 입니다. `timed_out` 은 없습니다.
"""

from __future__ import annotations

from enum import StrEnum


class WorkflowRunStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    WAITING_RUN = "waiting_run"
    WAITING_APPROVAL = "waiting_approval"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


_S = WorkflowRunStatus

TERMINAL_STATUSES: frozenset[WorkflowRunStatus] = frozenset({_S.SUCCEEDED, _S.FAILED, _S.CANCELLED})

_TRANSITIONS: dict[WorkflowRunStatus, frozenset[WorkflowRunStatus]] = {
    _S.QUEUED: frozenset({_S.RUNNING, _S.CANCELLED}),
    _S.RUNNING: frozenset(
        {_S.WAITING_RUN, _S.WAITING_APPROVAL, _S.SUCCEEDED, _S.FAILED, _S.CANCELLED}
    ),
    _S.WAITING_RUN: frozenset({_S.RUNNING, _S.FAILED, _S.CANCELLED}),
    _S.WAITING_APPROVAL: frozenset({_S.RUNNING, _S.FAILED, _S.CANCELLED}),
    _S.SUCCEEDED: frozenset(),
    _S.FAILED: frozenset(),
    _S.CANCELLED: frozenset(),
}


def can_transition(source: WorkflowRunStatus, target: WorkflowRunStatus) -> bool:
    """종결 상태에서 나가는 전이는 없습니다. `cancelled` 는 대기 중에도 가능합니다."""
    return target in _TRANSITIONS[source]


class IllegalWorkflowTransition(Exception):
    """전이표에 없는 전이를 시도했습니다. 종결 상태에서 나가는 전이를 포함합니다."""

    def __init__(self, source: WorkflowRunStatus, target: WorkflowRunStatus) -> None:
        super().__init__(f"illegal workflow transition: {source.value} -> {target.value}")
        self.source = source
        self.target = target
