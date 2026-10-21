"""spec 0007 2.3 (P5-1): `ApplyWorkflowNodeStatus` 의 구현 -- 저장소에 그대로 위임합니다.

`status_seq` 단조 규칙은 저장소의 한 문장(`INSERT … ON CONFLICT DO UPDATE … WHERE`)이 소유합니다.
"""

from __future__ import annotations

from aether_api.application.ports.outbound.workflow_node_state_projection_store import (
    WorkflowNodeStateProjectionStore,
)
from aether_api.domain.workflow_node_status_message import WorkflowNodeStatusMessage


class ApplyWorkflowNodeStatusUseCase:
    def __init__(self, store: WorkflowNodeStateProjectionStore) -> None:
        self._store = store

    def __call__(self, message: WorkflowNodeStatusMessage) -> bool:
        return self._store.apply_status(message)
