"""spec 0005 2.1, 2.9 개정 2 (P4-2a A): `HandleWorkflowRequested` - worker 의 소비자
(`adapters/inbound/stream`)가 `aether:workflow_runs:requested` 에서 받은 메시지마다 부르는
inbound 포트. `HandleRunRequested`(Agent Run)와 **같은 모양, 다른 포트**입니다 - 다른 스트림이고
다른 값 객체입니다. `WorkflowHandleOutcome.ack` 이 소비자가 `XACK` 할지를 정합니다.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from aether_workflow.domain.run_status import WorkflowRunStatus


@dataclass(frozen=True)
class WorkflowRequestedMessage:
    """`aether:workflow_runs:requested` 한 항목을 파싱한 값. `traceparent` 가 빈 문자열이면
    `None` 입니다(api 는 없을 때 빈 문자열을 싣습니다)."""

    message_id: str
    workflow_run_id: UUID
    workflow_version_id: UUID
    traceparent: str | None


@dataclass(frozen=True)
class WorkflowHandleOutcome:
    """`ack=True` 면 소비자가 `XACK` 합니다. `status` 는 전진이 끝난 경우의 `WorkflowRunStatus`
    (로그·관측용 - 소비자는 이 값으로 분기하지 않습니다)."""

    ack: bool
    status: WorkflowRunStatus | None


class HandleWorkflowRequested(Protocol):
    def __call__(self, message: WorkflowRequestedMessage) -> WorkflowHandleOutcome: ...
