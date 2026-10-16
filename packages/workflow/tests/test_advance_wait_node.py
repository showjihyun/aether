"""spec 0005 2.7 개정 7 (5), R-11, D-4 (P4-3 둘째 물결): `AdvanceWorkflowRunUseCase` 의 `WAIT` 노드
-
fake 포트와 **주입된 시계**로, 컨테이너 없이(AR-9).

증명하는 것: `WAIT` 에 닿으면 Run 이 `waiting_timer` + `wake_at` 으로 파킹되고 lease 를 놓는다 /
`wake_at` 전의 깨움은 아무 것도 바꾸지 않는다(이벤트·통지·`seq` 증가 없음) / 시계를 앞으로 돌리면
노드를 마치고 다음으로 간다 / **테스트 소요가 대기 시간과 무관**하다(실제로 기다리지 않는다) /
`wake_at` 은 `waiting_timer` 일 때만 값이 있다(상태에서 유도) / 시작만 하고 죽은 `WAIT` 도 같은 길로
파킹된다 / 새 이벤트 타입이 없다.
"""

from __future__ import annotations

import time
from datetime import timedelta
from uuid import UUID

import pytest
from aether_runtime.domain.run import RunStatus
from aether_workflow.application.usecases.advance_workflow_run import AdvanceWorkflowRunUseCase
from aether_workflow.domain.events import WORKFLOW_EVENT_TYPES
from aether_workflow.domain.failure import WorkflowFailureReason
from aether_workflow.domain.node import Edge, Node, NodeKind
from aether_workflow.domain.node_execution import NodeExecutionRecord, NodeExecutionStatus
from aether_workflow.domain.run_execution import WorkflowRunExecution
from aether_workflow.domain.run_status import WorkflowRunStatus

from packages.workflow.tests.fakes import (
    FakeAgentRunLauncher,
    FakeAgentRunReader,
    FakeApprovalReader,
    FakeWorkflowClock,
    FakeWorkflowEventSink,
    FakeWorkflowRunDeclarationReader,
    FakeWorkflowRunStateStore,
    FakeWorkflowStatusNotifier,
)

_AGENT = UUID("00000000-0000-0000-0000-0000000000a1")


class _Rig:
    def __init__(self) -> None:
        self.store = FakeWorkflowRunStateStore()
        self.reader = FakeWorkflowRunDeclarationReader()
        self.sink = FakeWorkflowEventSink()
        self.notifier = FakeWorkflowStatusNotifier()
        self.clock = FakeWorkflowClock()
        self.agent_runs = FakeAgentRunReader()
        self.agent_runs.add_version(_AGENT, None)
        self.launcher = FakeAgentRunLauncher(self.store)
        self.advance = AdvanceWorkflowRunUseCase(
            self.store,
            self.reader,
            self.sink,
            self.notifier,
            self.clock,
            agent_runs=self.agent_runs,
            approvals=FakeApprovalReader(),
            launcher=self.launcher,
            owner="worker-a",
            lease_ttl_seconds=60.0,
        )

    def declare(self, wait_seconds: int | None = 3600) -> UUID:
        return self.reader.add(
            (
                Node("start", NodeKind.START),
                Node("w", NodeKind.WAIT, wait_seconds=wait_seconds),
                Node("end", NodeKind.END),
            ),
            (Edge("start", "w"), Edge("w", "end")),
        )

    def execution(self, run_id: UUID) -> WorkflowRunExecution:
        execution = self.store.load(run_id)
        assert execution is not None
        return execution

    def record(self, run_id: UUID, node_id: str) -> NodeExecutionRecord:
        (record,) = (r for r in self.store.node_executions(run_id) if r.node_id == node_id)
        return record

    def counts(self) -> tuple[int, int, int]:
        return len(self.sink.events), len(self.notifier.messages), len(self.store.set_status_calls)


def test_reaching_a_wait_node_parks_the_run_with_the_wake_time() -> None:
    """개정 7 (5): `WAIT` 에 닿으면 노드 실행을 시작하고 `wake_at = now + wait_seconds` 를 계산해
    Workflow Run 을 `waiting_timer` + `wake_at` 으로 파킹한다 - 노드 실행도 `waiting_timer` 다."""
    rig = _Rig()
    run_id = rig.declare(3600)
    before = rig.clock.peek()

    assert rig.advance(run_id) is WorkflowRunStatus.WAITING_TIMER

    execution = rig.execution(run_id)
    assert execution.status is WorkflowRunStatus.WAITING_TIMER
    assert execution.current_node_id == "w"
    assert execution.wake_at is not None
    assert timedelta(seconds=3600) < execution.wake_at - before <= timedelta(seconds=3600 + 60)
    assert rig.record(run_id, "w").status is NodeExecutionStatus.WAITING_TIMER
    assert rig.store.lease_owner[run_id] is None, "R-7: 대기 중에 lease 를 쥐지 않는다"
    parked = rig.notifier.messages[-1]
    assert parked.status is WorkflowRunStatus.WAITING_TIMER
    assert parked.wake_at == execution.wake_at
    assert parked.waiting_run_id is None and parked.waiting_node_execution_id is None


def test_the_parking_uses_the_existing_event_vocabulary_only() -> None:
    """개정 7 (5): 이벤트는 `workflow.status` 하나로 충분하다 - 새 이벤트 타입이 없다."""
    rig = _Rig()
    run_id = rig.declare()

    rig.advance(run_id)

    assert {e.type for e in rig.sink.events} <= WORKFLOW_EVENT_TYPES
    statuses = [e.payload.get("status") for e in rig.sink.events if e.type == "workflow.status"]
    assert statuses[-1] == "waiting_timer"
    assert "wake_at" not in rig.sink.events[-1].payload


def test_a_wake_signal_before_the_wake_time_changes_nothing() -> None:
    """R-8 의 대기판: `wake_at` 전의 깨움(중복·이른 재큐)은 파킹을 유지한 채 돌아간다 - 이벤트·통지·
    `seq` 증가가 없고 `wake_at` 도 그대로다."""
    rig = _Rig()
    run_id = rig.declare(3600)
    rig.advance(run_id)
    before = rig.execution(run_id)
    counts = rig.counts()

    for _ in range(3):
        assert rig.advance(run_id) is WorkflowRunStatus.WAITING_TIMER

    after = rig.execution(run_id)
    assert rig.counts() == counts
    assert (after.status_seq, after.wake_at) == (before.status_seq, before.wake_at)
    assert rig.record(run_id, "w").status is NodeExecutionStatus.WAITING_TIMER
    assert rig.store.lease_owner[run_id] is None


def test_moving_the_clock_forward_ends_the_wait_and_finishes_the_run() -> None:
    """R-11: 시계를 앞으로 돌리면 대기가 끝나고 노드를 마친 뒤 다음으로 간다."""
    rig = _Rig()
    run_id = rig.declare(3600)
    rig.advance(run_id)
    assert rig.execution(run_id).wake_at is not None
    rig.clock.jump(3600 + 60)

    assert rig.advance(run_id) is WorkflowRunStatus.SUCCEEDED

    assert rig.record(run_id, "w").status is NodeExecutionStatus.SUCCEEDED
    assert rig.record(run_id, "end").status is NodeExecutionStatus.SUCCEEDED
    finished = [
        e for e in rig.sink.events if e.type == "node.finished" and e.payload["node_id"] == "w"
    ]
    assert len(finished) == 1, "대기가 끝나도 노드는 한 번만 마친다"
    assert [r.node_id for r in rig.store.node_executions(run_id)] == ["start", "w", "end"]
    assert rig.advance(run_id) is WorkflowRunStatus.SUCCEEDED, "멱등"


def test_the_wait_is_not_over_before_the_wake_time_and_is_over_after_it() -> None:
    """경계: 시계가 `wake_at` 에 못 미치면 아직이고, 지나면 끝난다."""
    rig = _Rig()
    run_id = rig.declare(100)
    rig.advance(run_id)
    wake_at = rig.execution(run_id).wake_at
    assert wake_at is not None

    rig.clock.jump((wake_at - rig.clock.peek()).total_seconds() - 10)
    assert rig.advance(run_id) is WorkflowRunStatus.WAITING_TIMER

    rig.clock.jump(20)
    assert rig.advance(run_id) is WorkflowRunStatus.SUCCEEDED


@pytest.mark.parametrize("wait_seconds", [60, 3600, 365 * 24 * 3600])
def test_the_test_duration_does_not_depend_on_the_wait_duration(wait_seconds: int) -> None:
    """R-11: 대기 시간이 얼마든 테스트는 즉시 끝난다 - 실제 시간을 기다리지 않고 벽시계 소요가
    대기 시간과 무관하다."""
    rig = _Rig()
    run_id = rig.declare(wait_seconds)

    started = time.perf_counter()
    assert rig.advance(run_id) is WorkflowRunStatus.WAITING_TIMER
    rig.clock.jump(wait_seconds + 60)
    assert rig.advance(run_id) is WorkflowRunStatus.SUCCEEDED
    elapsed = time.perf_counter() - started

    assert elapsed < 1.0, f"{wait_seconds}s 대기가 벽시계로 {elapsed:.2f}s 걸렸다"


def test_wake_at_exists_only_while_the_run_is_waiting_for_the_timer() -> None:
    """개정 7 (5): `wake_at` 은 상태에서 유도된다 - `waiting_timer` 일 때만 값이 있고 대기가 끝나
    `running` 이 되면 지워진다(`waiting_run_id` 와 같은 규칙). 통지도 같다."""
    rig = _Rig()
    run_id = rig.declare(3600)
    rig.advance(run_id)
    assert rig.execution(run_id).wake_at is not None
    rig.clock.jump(4000)

    rig.advance(run_id)

    assert rig.execution(run_id).wake_at is None
    timer_messages = [
        m for m in rig.notifier.messages if m.status is WorkflowRunStatus.WAITING_TIMER
    ]
    assert len(timer_messages) == 1 and timer_messages[0].wake_at is not None
    assert all(
        m.wake_at is None
        for m in rig.notifier.messages
        if m.status is not WorkflowRunStatus.WAITING_TIMER
    )


def test_a_wait_started_but_not_parked_before_a_crash_parks_without_a_second_row() -> None:
    """R-6, R-8: `WAIT` 의 행만 만들고 죽었다 - 재전달은 새 행 없이 파킹한다."""
    rig = _Rig()
    run_id = rig.declare(3600)
    rig.store.seed(run_id, status=WorkflowRunStatus.RUNNING, status_seq=3, current_node_id="w")
    rig.store.seed_node(run_id, "start", NodeExecutionStatus.SUCCEEDED)
    rig.store.seed_node(run_id, "w", NodeExecutionStatus.RUNNING)

    assert rig.advance(run_id) is WorkflowRunStatus.WAITING_TIMER

    assert rig.record(run_id, "w").status is NodeExecutionStatus.WAITING_TIMER
    assert rig.execution(run_id).wake_at is not None


def test_a_node_parked_but_the_run_not_yet_saved_before_a_crash_parks_again() -> None:
    """노드만 `waiting_timer` 이고 Run 상태를 저장하기 전에 죽었다(`wake_at` 을 모른다) - 다시
    파킹하며 `wake_at` 을 정한다. 노드 행은 둘이 되지 않는다."""
    rig = _Rig()
    run_id = rig.declare(3600)
    rig.store.seed(run_id, status=WorkflowRunStatus.RUNNING, status_seq=3, current_node_id="w")
    rig.store.seed_node(run_id, "start", NodeExecutionStatus.SUCCEEDED)
    rig.store.seed_node(run_id, "w", NodeExecutionStatus.WAITING_TIMER)

    assert rig.advance(run_id) is WorkflowRunStatus.WAITING_TIMER

    assert rig.execution(run_id).wake_at is not None
    assert len([r for r in rig.store.node_executions(run_id) if r.node_id == "w"]) == 1


@pytest.mark.parametrize("wait_seconds", [None, 0, -1])
def test_a_wait_without_a_duration_that_slipped_past_validation_fails_the_run(
    wait_seconds: int | None,
) -> None:
    """저장 때 걸러지는 모양이지만(`wait_node_without_duration`) 실행기는 얼마나 기다릴지 모르는 채
    파킹하지 않는다 - 영원히 멈추는 Run 이 아니라 `invalid_graph` 로 끝난다."""
    rig = _Rig()
    run_id = rig.declare(wait_seconds)

    assert rig.advance(run_id) is WorkflowRunStatus.FAILED
    assert rig.execution(run_id).failure_reason == WorkflowFailureReason.INVALID_GRAPH.value
    assert rig.record(run_id, "w").status is NodeExecutionStatus.FAILED


def test_a_wait_inside_a_parallel_branch_parks_the_run_and_the_other_branch_follows() -> None:
    """`PARALLEL` 의 분기 안 `WAIT`: 분기 안의 파킹은 Run 전체를 파킹하고, 대기가 끝나면 남은
    분기를 잇고 `JOIN` 이 모두를 기다린다(개정 7 (1))."""
    rig = _Rig()
    nodes = (
        Node("start", NodeKind.START),
        Node("p", NodeKind.PARALLEL),
        Node("w", NodeKind.WAIT, wait_seconds=600),
        Node("a", NodeKind.AGENT, agent_id=_AGENT),
        Node("j", NodeKind.JOIN),
        Node("end", NodeKind.END),
    )
    edges = (
        Edge("start", "p"),
        Edge("p", "w"),
        Edge("p", "a"),
        Edge("w", "j"),
        Edge("a", "j"),
        Edge("j", "end"),
    )
    run_id = rig.reader.add(nodes, edges)

    assert rig.advance(run_id) is WorkflowRunStatus.WAITING_TIMER
    assert "a" not in [r.node_id for r in rig.store.node_executions(run_id)]
    rig.clock.jump(700)
    assert rig.advance(run_id) is WorkflowRunStatus.WAITING_RUN
    (child,) = [r for r in rig.store.node_executions(run_id) if r.node_id == "a"]
    assert child.agent_run_id is not None
    rig.agent_runs.set_status(child.agent_run_id, RunStatus.SUCCEEDED)
    rig.agent_runs.set_text(child.agent_run_id, "ok")

    assert rig.advance(run_id) is WorkflowRunStatus.SUCCEEDED

    assert rig.record(run_id, "j").output == {
        "branches": {"w": None, "a": {"text": "ok", "status": "succeeded"}}
    }
