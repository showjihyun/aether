"""spec 0005 2.4, 2.9: 노드 실행 기록(`data.workflow_node_executions`)의 값 객체.

`NodeExecutionStatus` 는 P4-1 이 `status` 를 `text` 로 열어 두고 "실행기가 집합을 정한다" 고
남긴 그 집합입니다. 지금은 `running`·`succeeded`·`failed` 셋입니다. **컬럼을 enum 으로 좁히는
것은 PR B** 입니다 — 파킹이 `waiting_run` 을 더하므로 그때 한 번에 좁힙니다(지금 좁히면
마이그레이션이 두 번 필요합니다).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID


class NodeExecutionStatus(StrEnum):
    RUNNING = "running"
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
