"""spec 0005 2.5 개정 3, R-8, D-4 (P4-2a B2): `ResumeParkedWorkflowsUseCase` --
`ResumeParkedWorkflows` 의
구현. 깨우는 신호 둘의 **공통 일은 재큐 하나**입니다.

이 유스케이스는 Workflow 의 상태를 읽어 결론내지 않습니다 - 찾은 만큼 재큐할 뿐이고, 재큐된 요청이
실행기(`AdvanceWorkflowRunUseCase`)에 닿으면 실행기가 자식의 상태를 보고 전진할지 파킹을 유지할지
정합니다. 그래서 같은 Workflow 를 빠른 경로와 스위퍼가 **둘 다** 재큐해도(R-8) 노드는 한 번만
전진합니다. 경로가 둘인 이유는 이벤트 하나가 유실되면 Workflow 가 영원히 파킹되기 때문이고,
안전망은 "이벤트만 믿지 않는다" 의 제품판입니다(`improvement-log/2026-10-11-001`).
"""

from __future__ import annotations

from uuid import UUID

from aether_worker.application.ports.outbound.parked_workflow_finder import (
    ParkedWorkflow,
    ParkedWorkflowFinder,
)
from aether_worker.application.ports.outbound.workflow_requeuer import WorkflowRequeuer


class ResumeParkedWorkflowsUseCase:
    def __init__(self, finder: ParkedWorkflowFinder, requeuer: WorkflowRequeuer) -> None:
        self._finder = finder
        self._requeuer = requeuer

    def on_agent_run_finished(self, agent_run_id: UUID) -> int:
        return self._requeue_all(self._finder.waiting_on(agent_run_id))

    def sweep(self) -> int:
        return self._requeue_all(self._finder.ready_to_resume())

    def _requeue_all(self, parked: tuple[ParkedWorkflow, ...]) -> int:
        for workflow in parked:
            self._requeuer.requeue(workflow)
        return len(parked)
