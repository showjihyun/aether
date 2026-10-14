"""spec 0005 2.5 개정 3 (P4-2a B2): `WorkflowRequeuer` -- 파킹된 Workflow Run 을 요청 스트림에 다시
싣습니다. 깨우는 신호 둘(종결 통지·스위퍼)이 하는 일은 **이것 하나**이고, 판정은 실행기가 합니다.
"""

from __future__ import annotations

from typing import Protocol

from aether_worker.application.ports.outbound.parked_workflow_finder import ParkedWorkflow


class WorkflowRequeuer(Protocol):
    def requeue(self, workflow: ParkedWorkflow) -> None:
        """`aether:workflow_runs:requested` 에 `XADD`. 같은 Workflow 를 두 번 실어도 안전합니다 -
        실행기가 멱등입니다(R-8). 실패하면 예외를 올립니다."""
        ...
