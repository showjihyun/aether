"""spec 0007 2.3 (P5-1): 노드 실행 투영 유스케이스 인터페이스. 소비자는 이 포트 타입만 보고
부릅니다(AR-12)."""

from __future__ import annotations

from typing import Protocol

from aether_api.domain.workflow_node_status_message import WorkflowNodeStatusMessage


class ApplyWorkflowNodeStatus(Protocol):
    """적용됐으면 `True`, 늦은(같거나 낮은 `status_seq`) 메시지면 `False` -- 소비자는 어느 쪽이든
    ack 합니다(멱등 무시)."""

    def __call__(self, message: WorkflowNodeStatusMessage) -> bool: ...
