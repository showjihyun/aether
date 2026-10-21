"""spec 0007 2.3, D-3, D-4 (P5-1): `WorkflowNodeStatusMessage`·`WorkflowNodeStatusNotifier` --
`aether:workflow_node_states:status` 로 가는 노드 실행 투영 통지.

`aether:workflow_runs:status` 를 넓히지 않고 **새 스트림**을 둔 이유: 그 스트림의 소비자가 둘이라
(api 투영 group `aether-api`, 파킹 깨우기 group `aether-workflow`) 필드를 늘리면 둘 다 영향을
받습니다.

`status_seq` 는 그 노드 상태 변경을 낳은 `workflow.*` 이벤트의 `seq` 와 같은 수열입니다 - Workflow
Run 하나 안에서 단조 증가하므로 `(workflow_run_id, node_id)` 키 안에서도 단조입니다.
**노드 출력(`output`)은 이 메시지에 없습니다**(D-4): 출력은 `data` 평면에 머뭅니다.
"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol
from uuid import UUID

from pydantic import BaseModel

from aether_workflow.domain.failure import WorkflowFailureReason
from aether_workflow.domain.node import NodeKind
from aether_workflow.domain.node_execution import NodeExecutionStatus


class WorkflowNodeStatusMessage(BaseModel):
    workflow_run_id: UUID
    node_id: str
    kind: NodeKind
    status: NodeExecutionStatus
    status_seq: int
    started_at: datetime | None = None
    finished_at: datetime | None = None
    failure_reason: WorkflowFailureReason | None = None


class WorkflowNodeStatusNotifier(Protocol):
    def notify(self, message: WorkflowNodeStatusMessage) -> None: ...
