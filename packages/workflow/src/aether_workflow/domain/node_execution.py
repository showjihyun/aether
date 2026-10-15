"""spec 0005 2.4, 2.9: 노드 실행 기록(`data.workflow_node_executions`)의 값 객체.

`NodeExecutionStatus` 는 P4-1 이 `status` 를 `text` 로 열어 두고 "실행기가 집합을 정한다" 고
남긴 그 집합입니다. `running`·`waiting_run`·`succeeded`·`failed` 넷입니다. 컬럼은 마이그레이션 0007
이
`data.workflow_node_execution_status` enum 으로 좁혔습니다(`data.run_execution_status` 와 **다른
타입**). `waiting_run` 은 자식 Agent Run 을 기다리는 `AGENT` 노드이고, 자식 Run 의 id 는
`agent_run_id` 에 **발사 전에** 영속됩니다(R-8).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID


class NodeExecutionStatus(StrEnum):
    RUNNING = "running"
    WAITING_RUN = "waiting_run"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


@dataclass(frozen=True)
class NodeExecutionRecord:
    """`unique(workflow_run_id, node_id, iteration)` 한 행."""

    id: UUID
    workflow_run_id: UUID
    node_id: str
    iteration: int
    status: NodeExecutionStatus
    started_at: datetime
    finished_at: datetime | None
    agent_run_id: UUID | None = None
    failure_reason: str | None = None
    output: dict[str, Any] | None = None
    """spec 0005 2.4: 노드의 출력(JSON 객체). `START`·`END` 는 `None`. 읽는 곳은 `CONDITION` 판정의
    맥락 하나뿐입니다(C-3)."""
    output_truncated: bool = False
