"""spec 0007 2.3, D-4 (P5-1): `WorkflowNodeStatusMessage` --
`aether:workflow_node_states:status` 로 들어오는 노드 실행 상태 통지의 api 쪽 값 객체.

worker 쪽 `WorkflowNodeStatusMessage` 와 필드가 같지만 서로 import 하지 않습니다 -- 스트림 계약이
정본입니다(`workflow_run_status_message.py` 와 같은 선). **노드 출력은 이 계약에 없습니다**(D-4):
필드가 늘어도 모르는 필드는 무시됩니다(`extra="ignore"`)가, 출력을 싣는 것은 계약 위반입니다.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from aether_workflow.domain.node_execution import NodeExecutionStatus
from pydantic import BaseModel, ConfigDict


class WorkflowNodeStatusMessage(BaseModel):
    model_config = ConfigDict(extra="ignore")

    workflow_run_id: UUID
    node_id: str
    kind: str
    status: NodeExecutionStatus
    status_seq: int
    started_at: datetime | None = None
    finished_at: datetime | None = None
    failure_reason: str | None = None
