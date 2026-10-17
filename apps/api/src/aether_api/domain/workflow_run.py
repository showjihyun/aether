"""spec 0005 2.3, 2.9 개정 2, R-13: Control Plane 의 Workflow Run 투영 값 객체와 예외.

`WorkflowRunView` 는 `control.workflow_runs` 한 행(투영)을 `control.workflow_versions` 와
JOIN 해 `workflow_id`·`workflow_version`(번호)까지 담습니다. 실행 상태의 정본은
`data.workflow_run_executions` 이고(worker 가 씁니다) 여기 값은 `aether:workflow_runs:status`
스트림으로 api 가 갱신한 **투영**입니다. `status` 는 `aether_workflow.domain.run_status` 의
타입을 그대로 씁니다 — api 는 `aether_workflow.domain` 만 import 합니다.

`waiting_run_id` 는 `waiting_run` 상태에서 기다리는 자식 Agent Run 의 id 입니다(R-13 의
절반 — 조회에 나타납니다). `waiting_node_execution_id` 는 `waiting_approval` 상태에서 승인이
지목해야 하는 노드 실행의 id 입니다(P4-4, R-12) - 같은 모양의 투영이고 같은 불변식입니다.
`wake_at` 은 `waiting_timer` 상태에서 `WAIT` 노드가 깨어날 시각입니다(P4-3, spec 0005 2.7 개정 7
(5)) - 역시 상태에서 유도되는 투영입니다.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from aether_workflow.domain.run_status import WorkflowRunStatus


@dataclass(frozen=True)
class WorkflowRunView:
    """`GET /workflow-runs/{id}` 의 정본 — `control.workflow_runs` 투영."""

    workflow_run_id: UUID
    workflow_id: UUID
    workflow_version: int
    workflow_version_id: UUID
    status: WorkflowRunStatus
    current_node_id: str | None
    waiting_run_id: UUID | None
    waiting_node_execution_id: UUID | None
    requested_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    failure_reason: str | None
    wake_at: datetime | None = None


class WorkflowRunNotFound(Exception):
    """주어진 `workflow_run_id` 의 Workflow Run 이 없습니다."""

    def __init__(self, workflow_run_id: UUID) -> None:
        super().__init__(str(workflow_run_id))
        self.workflow_run_id = workflow_run_id


@dataclass(frozen=True)
class WorkflowRunPage:
    """`GET /workflow-runs` 의 커서 페이지(투영) - `next_cursor` 는 불투명."""

    items: list[WorkflowRunView]
    next_cursor: str | None
