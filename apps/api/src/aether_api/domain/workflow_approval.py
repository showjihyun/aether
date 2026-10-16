"""spec 0005 2.6 개정 5, R-8, R-12, C-4 (P4-4): 승인 기록 값 객체와 거부 사유 예외.

`approved_by` 는 **인증된 주체의 id 를 그대로 적은 문자열** 입니다 - 이 모듈 어디에도
"누가 승인할 수 있는가" 를 묻는 규칙이 없습니다(승인자 권한 모델은 만들지 않습니다,
Phase 8 의 자리). 아래 예외 셋은 전부 **정확성** 가드입니다: 선승인·엉뚱한 노드 실행
지목·재전송을 막을 뿐 주체를 보지 않습니다.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class WorkflowApprovalView:
    """`control.workflow_approvals` 한 행 - 승인 기록(append-only)."""

    workflow_run_id: UUID
    node_execution_id: UUID
    approved_by: str
    approved_at: datetime
    note: str | None


class WorkflowRunNotWaitingApproval(Exception):
    """그 Workflow Run 이 `waiting_approval` 이 아닙니다(선승인 또는 이미 지난 대기)."""

    def __init__(self, workflow_run_id: UUID) -> None:
        super().__init__(str(workflow_run_id))
        self.workflow_run_id = workflow_run_id


class NodeExecutionNotWaiting(Exception):
    """지목한 노드 실행이 그 Run 이 지금 기다리는 것이 아닙니다(R-12 의 핵심)."""

    def __init__(self, workflow_run_id: UUID, node_execution_id: UUID) -> None:
        super().__init__(f"{workflow_run_id}/{node_execution_id}")
        self.workflow_run_id = workflow_run_id
        self.node_execution_id = node_execution_id


class AlreadyApproved(Exception):
    """그 노드 실행의 승인이 이미 기록돼 있습니다(`unique(workflow_run_id, node_execution_id)`)."""

    def __init__(self, workflow_run_id: UUID, node_execution_id: UUID) -> None:
        super().__init__(f"{workflow_run_id}/{node_execution_id}")
        self.workflow_run_id = workflow_run_id
        self.node_execution_id = node_execution_id
