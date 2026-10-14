"""spec 0005 2.1, 2.3: `AdvanceWorkflowRun` — worker 가 부르는 유일한 문.

다른 worker 가 이 Workflow Run 의 lease 를 이미 쥐고 있으면 `WorkflowLeaseHeld` 를 냅니다 —
`aether_runtime.domain.run.LeaseHeld` 와 같은 뜻이지만 **자기 것**으로 선언합니다
(`aether_workflow` 는 `aether_runtime` 에 기대지 않습니다, D-13). 호출자는 그 예외를 보고
메시지를 ack 하지 않습니다.
"""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from aether_workflow.domain.run_status import WorkflowRunStatus


class WorkflowLeaseHeld(Exception):
    def __init__(self, workflow_run_id: UUID) -> None:
        super().__init__(f"lease already held for workflow run {workflow_run_id}")
        self.workflow_run_id = workflow_run_id


class AdvanceWorkflowRun(Protocol):
    def __call__(self, workflow_run_id: UUID) -> WorkflowRunStatus: ...
