"""spec 0007 2.3 (P5-1): `ApplyWorkflowNodeStatusUseCase` -- 저장소에 위임만 한다. `status_seq` 단조
규칙은 저장소(SQL)가 소유하고 `test_workflow_node_projection_integration.py` 가 증명한다.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from aether_api.application.usecases.apply_workflow_node_status import (
    ApplyWorkflowNodeStatusUseCase,
)
from aether_api.domain.workflow_node_status_message import WorkflowNodeStatusMessage
from aether_workflow.domain.node_execution import NodeExecutionStatus


class _Store:
    def __init__(self, result: bool) -> None:
        self.calls: list[WorkflowNodeStatusMessage] = []
        self._result = result

    def apply_status(self, message: WorkflowNodeStatusMessage) -> bool:
        self.calls.append(message)
        return self._result


def _message() -> WorkflowNodeStatusMessage:
    return WorkflowNodeStatusMessage(
        workflow_run_id=uuid4(),
        node_id="a",
        kind="AGENT",
        status=NodeExecutionStatus.RUNNING,
        status_seq=1,
    )


@pytest.mark.parametrize("applied", [True, False])
def test_the_store_decision_is_returned_unchanged(applied: bool) -> None:
    store = _Store(applied)
    message = _message()

    assert ApplyWorkflowNodeStatusUseCase(store)(message) is applied
    assert store.calls == [message]
