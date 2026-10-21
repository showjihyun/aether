"""spec 0007 2.3 (P5-2): 노드 실행 조회 유스케이스 인터페이스. HTTP 어댑터는 이 포트 타입만 보고
부릅니다(AR-12)."""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from aether_api.domain.workflow_node_state import WorkflowNodeStatePage


class ListWorkflowRunNodes(Protocol):
    """한 Workflow Run 의 노드 상태를 페이지로 돌려줍니다. 페이지 규칙은 `ListAgents` 와 같습니다.

    Run 이 없으면 `WorkflowRunNotFound` 를 던집니다(빈 목록이 아닙니다).
    """

    def __call__(
        self, workflow_run_id: UUID, limit: int, cursor: str | None
    ) -> WorkflowNodeStatePage: ...
