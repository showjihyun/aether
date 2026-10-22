"""spec 0007 2.3, D-3, D-4 (P5-2): 노드 실행 투영(`control.workflow_node_states`)의 읽기 값 객체.

화면이 쓰는 열만 있습니다 - 노드 출력·입력·자식 Run id 는 없습니다(D-4). `status` 는
`aether_workflow.domain.node_execution` 의 타입을 그대로 씁니다(api 는 `aether_workflow.domain`
만 import 합니다).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from aether_workflow.domain.node_execution import NodeExecutionStatus


@dataclass(frozen=True)
class WorkflowNodeStateView:
    """한 Workflow Run 안의 노드 하나의 가장 최근 상태."""

    node_id: str
    kind: str
    status: NodeExecutionStatus
    started_at: datetime | None
    finished_at: datetime | None
    failure_reason: str | None


@dataclass(frozen=True)
class WorkflowNodeStatePage:
    """`GET /workflow-runs/{id}/nodes` 의 커서 페이지 - `next_cursor` 는 불투명."""

    items: list[WorkflowNodeStateView]
    next_cursor: str | None
