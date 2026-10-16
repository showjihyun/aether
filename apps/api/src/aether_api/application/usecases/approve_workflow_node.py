"""spec 0005 2.6 개정 5, R-8, R-12, C-4 (P4-4): `ApproveWorkflowNode` 포트의 구현 - 검사 → 기록 →
재큐.

**여기에 권한 판정이 없습니다.** 인증된 주체 누구나 승인할 수 있고, "요청자 본인은 승인할 수 없다"
같은 규칙도 두지 않습니다(그것이 곧 권한 모델이고 Phase 8 의 자리입니다). `approved_by` 는 호출자가
건넨 주체 id 를 그대로 적습니다. 아래 검사는 전부 **정확성** 입니다:

1. 없는 Workflow Run -> `WorkflowRunNotFound`.
2. 이미 승인됐다 -> `AlreadyApproved`. **상태 검사보다 먼저**입니다: 실행기가 이미 전진해 Run 이
   `waiting_approval` 이 아니게 된 뒤의 재전송도 "이미 승인됨" 이어야 클라이언트가 재전송 성공을
   구별합니다(R-8).
3. Run 이 `waiting_approval` 이 아님 -> `WorkflowRunNotWaitingApproval`(선승인 방지).
4. 지목한 노드 실행이 그 Run 이 기다리는 것이 아님 -> `NodeExecutionNotWaiting`(R-12).
   기다리는 대상은 `control` 의 투영(`waiting_node_execution_id`)에서 읽습니다 - api 는
   `data` 를 볼 수 없습니다. 투영에 값이 없으면(대기라는데 지목 대상 미상) 어떤 노드
   실행도 인정하지 않습니다(fail-closed).

기록은 `unique(workflow_run_id, node_execution_id)` 로 DB 가 한 번 더 지킵니다(동시 요청의 경쟁).

기록한 **뒤에** `WorkflowRunNotifier.requested` 로 재큐합니다. 실행기는 재큐 메시지가 아니라 저장된
승인을 읽어 전진하므로 순서가 이래야 합니다. 재큐(XADD) 실패는 WARNING 만 남기고 승인을
막지 않습니다 - 승인 기록은 남았고, 유실되면 스위퍼가 승인이 있는 `waiting_approval`
도 주워 재큐합니다.
"""

from __future__ import annotations

import logging
from uuid import UUID

from aether_workflow.domain.run_status import WorkflowRunStatus

from aether_api.application.ports.outbound.workflow_approval_store import WorkflowApprovalStore
from aether_api.application.ports.outbound.workflow_run_declaration_store import (
    WorkflowRunDeclarationStore,
)
from aether_api.application.ports.outbound.workflow_run_notifier import WorkflowRunNotifier
from aether_api.domain.workflow_approval import (
    AlreadyApproved,
    NodeExecutionNotWaiting,
    WorkflowApprovalView,
    WorkflowRunNotWaitingApproval,
)
from aether_api.domain.workflow_run import WorkflowRunNotFound

logger = logging.getLogger(__name__)


class ApproveWorkflowNodeUseCase:
    def __init__(
        self,
        runs: WorkflowRunDeclarationStore,
        approvals: WorkflowApprovalStore,
        notifier: WorkflowRunNotifier,
    ) -> None:
        self._runs = runs
        self._approvals = approvals
        self._notifier = notifier

    def __call__(
        self, workflow_run_id: UUID, node_execution_id: UUID, approved_by: str, note: str | None
    ) -> WorkflowApprovalView:
        run = self._runs.get(workflow_run_id)
        if run is None:
            raise WorkflowRunNotFound(workflow_run_id)
        if self._approvals.get(workflow_run_id, node_execution_id) is not None:
            raise AlreadyApproved(workflow_run_id, node_execution_id)
        if run.status is not WorkflowRunStatus.WAITING_APPROVAL:
            raise WorkflowRunNotWaitingApproval(workflow_run_id)
        if run.waiting_node_execution_id != node_execution_id:
            raise NodeExecutionNotWaiting(workflow_run_id, node_execution_id)

        approval = self._approvals.record(workflow_run_id, node_execution_id, approved_by, note)

        try:
            self._notifier.requested(workflow_run_id, run.workflow_version_id, None)
        except Exception:  # noqa: BLE001 -- XADD 실패는 WARNING 만, 승인은 막지 않습니다
            logger.warning(
                "workflow_approval.requeue_failed",
                extra={
                    "workflow_run_id": str(workflow_run_id),
                    "node_execution_id": str(node_execution_id),
                },
            )
        return approval
