"""spec 0005 2.2, 2.3, R-13: Workflow Run 유스케이스 인터페이스.

HTTP 어댑터(`adapters/inbound/http/workflow_runs.py`)와 투영 소비자는 이 포트 타입만 보고
부릅니다(AR-12) — 구현은 조립(`main.py`)이 건네줍니다.
"""

from __future__ import annotations

from typing import Any, Protocol
from uuid import UUID

from aether_api.domain.workflow_run import WorkflowRunView
from aether_api.domain.workflow_run_status_message import WorkflowRunStatusMessage


class StartWorkflowRun(Protocol):
    """`workflow_id` 의 Workflow 를 실행합니다 — `workflow_version` 이 없으면 현재 Version.

    Workflow 가 없으면 `WorkflowNotFound`, 지정한 Version 이 없으면
    `WorkflowVersionNotFound` 를 던집니다.
    """

    def __call__(
        self, workflow_id: UUID, input: dict[str, Any] | None, workflow_version: int | None
    ) -> WorkflowRunView: ...


class GetWorkflowRun(Protocol):
    """Workflow Run 의 투영을 돌려줍니다. 없으면 `WorkflowRunNotFound` 를 던집니다."""

    def __call__(self, workflow_run_id: UUID) -> WorkflowRunView: ...


class ApplyWorkflowRunStatus(Protocol):
    """`message.seq` 가 `control.workflow_runs.status_seq` 보다 클 때만 적용합니다.

    적용됐으면 `True`, 이미 적용된(같거나 낮은 `seq`) 메시지면 `False` — 소비자는 어느 쪽이든
    ack 합니다(멱등 무시).
    """

    def __call__(self, message: WorkflowRunStatusMessage) -> bool: ...
