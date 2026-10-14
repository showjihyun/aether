"""spec 0005 2.5 개정 3, R-8, D-4 (P4-2a B2): `ResumeParkedWorkflowsUseCase` -- 깨우는 신호 둘(자식
Run
종결 통지·스위퍼)이 **하는 일은 재큐 하나**다. 판정은 실행기가 한다.

fake 포트로 컨테이너 없이(AR-9). 이 유스케이스는 상태를 읽어 결론내지 않는다 -- 찾은 만큼 재큐할
뿐이라
같은 Workflow 를 두 경로가 둘 다 재큐해도 안전하다(실행기가 멱등, `test_advance_agent_node.py`).
"""

from __future__ import annotations

from uuid import UUID, uuid4

from aether_worker.application.ports.outbound.parked_workflow_finder import ParkedWorkflow
from aether_worker.application.usecases.resume_parked_workflows import (
    ResumeParkedWorkflowsUseCase,
)


class FakeParkedWorkflowFinder:
    def __init__(self) -> None:
        self.waiting: dict[UUID, tuple[ParkedWorkflow, ...]] = {}
        self.ready: tuple[ParkedWorkflow, ...] = ()
        self.lookups: list[UUID] = []

    def waiting_on(self, agent_run_id: UUID) -> tuple[ParkedWorkflow, ...]:
        self.lookups.append(agent_run_id)
        return self.waiting.get(agent_run_id, ())

    def ready_to_resume(self) -> tuple[ParkedWorkflow, ...]:
        return self.ready


class FakeWorkflowRequeuer:
    def __init__(self) -> None:
        self.requeued: list[ParkedWorkflow] = []

    def requeue(self, workflow: ParkedWorkflow) -> None:
        self.requeued.append(workflow)


def _parked() -> ParkedWorkflow:
    return ParkedWorkflow(workflow_run_id=uuid4(), workflow_version_id=uuid4())


def test_a_finished_child_requeues_the_workflow_parked_on_it() -> None:
    """빠른 경로: 종결한 자식 Run 을 기다리는 Workflow 를 찾아 재큐한다."""
    finder, requeuer = FakeParkedWorkflowFinder(), FakeWorkflowRequeuer()
    child, parked = uuid4(), _parked()
    finder.waiting[child] = (parked,)

    count = ResumeParkedWorkflowsUseCase(finder, requeuer).on_agent_run_finished(child)

    assert count == 1
    assert requeuer.requeued == [parked]


def test_a_finished_run_nobody_waits_on_requeues_nothing() -> None:
    """평범한 Agent Run 의 종결 통지는 거의 전부 이 경우다 -- 아무 일도 하지 않는다."""
    finder, requeuer = FakeParkedWorkflowFinder(), FakeWorkflowRequeuer()
    child = uuid4()

    count = ResumeParkedWorkflowsUseCase(finder, requeuer).on_agent_run_finished(child)

    assert count == 0
    assert requeuer.requeued == []
    assert finder.lookups == [child]


def test_sweep_requeues_every_workflow_whose_child_already_finished() -> None:
    """안전망: 신호를 놓쳤어도 `waiting_run` 인데 자식이 이미 종결인 건을 전부 주워 재큐한다."""
    finder, requeuer = FakeParkedWorkflowFinder(), FakeWorkflowRequeuer()
    finder.ready = (_parked(), _parked(), _parked())

    count = ResumeParkedWorkflowsUseCase(finder, requeuer).sweep()

    assert count == 3
    assert requeuer.requeued == list(finder.ready)


def test_sweep_with_nothing_ready_does_nothing() -> None:
    finder, requeuer = FakeParkedWorkflowFinder(), FakeWorkflowRequeuer()

    assert ResumeParkedWorkflowsUseCase(finder, requeuer).sweep() == 0
    assert requeuer.requeued == []
