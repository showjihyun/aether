"""spec 0005 2.1, 2.9 개정 2: `WorkflowRunNotifier` — `aether:workflow_runs:requested` 로 가는
실행 통지의 outbound 포트. Agent Run 의 `aether:runs:requested` 와 **다른 스트림**입니다.
"""

from __future__ import annotations

from typing import Protocol
from uuid import UUID


class WorkflowRunNotifier(Protocol):
    """`requested(workflow_run_id, workflow_version_id, traceparent)` — 실패해도 예외를 삼키지
    않습니다. 실패 시 `202` 를 막지 않는 것은 유스케이스(`StartWorkflowRunUseCase`)의
    책임입니다.
    """

    def requested(
        self, workflow_run_id: UUID, workflow_version_id: UUID, traceparent: str | None
    ) -> None: ...
