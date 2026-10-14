"""spec 0005 2.9 개정 2, 2.10: `ApplyWorkflowRunStatus` 포트의 구현 — 저장소에 그대로 위임합니다.

`seq` 단조 증가 규칙과 `COALESCE` 는 `WorkflowRunDeclarationStore.apply_status` (한 UPDATE)가
소유합니다 — 이 유스케이스는 `WorkflowRunStatusMessage` 를 저장소 시그니처로 펼칠 뿐입니다.
"""

from __future__ import annotations

from aether_api.application.ports.outbound.workflow_run_declaration_store import (
    WorkflowRunDeclarationStore,
)
from aether_api.domain.workflow_run_status_message import WorkflowRunStatusMessage


class ApplyWorkflowRunStatusUseCase:
    """`WorkflowRunDeclarationStore` 하나로 inbound 포트 `ApplyWorkflowRunStatus` 를 구현합니다."""

    def __init__(self, store: WorkflowRunDeclarationStore) -> None:
        self._store = store

    def __call__(self, message: WorkflowRunStatusMessage) -> bool:
        return self._store.apply_status(
            message.workflow_run_id,
            seq=message.seq,
            status=message.status,
            current_node_id=message.current_node_id,
            waiting_run_id=message.waiting_run_id,
            started_at=message.started_at,
            finished_at=message.finished_at,
            failure_reason=message.failure_reason,
        )
