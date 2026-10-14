"""spec 0005 2.1, 2.9 개정 2 (P4-2a A): `HandleWorkflowRequestedUseCase` -
`HandleWorkflowRequested` 의 구현. `handle_run_requested.py` 의 ack 규칙을 **그대로** 따릅니다.

- 정상(어떤 `WorkflowRunStatus` 로든 전진이 반환) -> ack.
- `WorkflowLeaseHeld`(다른 worker 가 쥐고 있음) -> ack 하지 않습니다. 메시지는 PEL 에 남고 다음
  `XAUTOCLAIM` 주기가 다시 봅니다.
- 선언 없음(`AdvanceWorkflowRunUseCase` 가 내는 `RuntimeError`) -> 독약 메시지이므로 WARNING 을
  남기고 ack 합니다 - ack 하지 않으면 같은 메시지가 영원히 PEL 에 남아 재시도를 반복합니다.
- 그 밖의 예외는 흡수하지 않고 올립니다 - 소비자가 ack 하지 않아 다음 `XAUTOCLAIM` 이 재시도합니다.
"""

from __future__ import annotations

import logging

from aether_workflow.application.ports.inbound.advance_workflow_run import (
    AdvanceWorkflowRun,
    WorkflowLeaseHeld,
)

from aether_worker.application.ports.inbound.handle_workflow_requested import (
    WorkflowHandleOutcome,
    WorkflowRequestedMessage,
)
from aether_worker.application.ports.outbound.trace_context import TraceContext

logger = logging.getLogger(__name__)


class HandleWorkflowRequestedUseCase:
    def __init__(self, advance: AdvanceWorkflowRun, trace_context: TraceContext) -> None:
        self._advance = advance
        self._trace_context = trace_context

    def __call__(self, message: WorkflowRequestedMessage) -> WorkflowHandleOutcome:
        with self._trace_context.activate(message.traceparent):
            try:
                status = self._advance(message.workflow_run_id)
            except WorkflowLeaseHeld:
                return WorkflowHandleOutcome(ack=False, status=None)
            except RuntimeError:
                logger.warning(
                    "worker.handle_workflow_requested.no_declaration",
                    extra={"workflow_run_id": str(message.workflow_run_id)},
                )
                return WorkflowHandleOutcome(ack=True, status=None)
        return WorkflowHandleOutcome(ack=True, status=status)
