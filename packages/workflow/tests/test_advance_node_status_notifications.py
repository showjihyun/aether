"""spec 0007 2.3, D-3, D-4, R-5 (P5-1): 실행기가 노드 실행 상태를 바꿀 때 노드 상태 통지를 낸다 --
fake 포트로, 컨테이너 없이(AR-9).

증명하는 것: 노드 상태가 바뀔 때마다 한 통지 / `status_seq` 는 그 변경을 낳은 `workflow.*` 이벤트의
`seq` 와 같은 수열이고 노드 키 안에서 단조 / 파킹(`waiting_run`)과 실패(사유)가 실린다 / 통지에는
노드 출력이 없다 / 통지 포트를 꽂지 않으면 아무 것도 바뀌지 않는다.
"""

from __future__ import annotations

from uuid import UUID

from aether_runtime.domain.run import RunStatus
from aether_workflow.application.ports.outbound.workflow_node_status_notifier import (
    WorkflowNodeStatusMessage,
)
from aether_workflow.application.usecases.advance_workflow_run import AdvanceWorkflowRunUseCase
from aether_workflow.domain.failure import WorkflowFailureReason
from aether_workflow.domain.node import Edge, Node, NodeKind
from aether_workflow.domain.node_execution import NodeExecutionStatus
from aether_workflow.domain.run_status import WorkflowRunStatus

from packages.workflow.tests.fakes import (
    FakeAgentRunLauncher,
    FakeAgentRunReader,
    FakeApprovalReader,
    FakeWorkflowClock,
    FakeWorkflowEventSink,
    FakeWorkflowNodeStatusNotifier,
    FakeWorkflowRunDeclarationReader,
    FakeWorkflowRunStateStore,
    FakeWorkflowStatusNotifier,
    start_end_graph,
)

_AGENT = UUID("00000000-0000-0000-0000-0000000000a1")


class _Rig:
    def __init__(self, *, with_node_notifier: bool = True) -> None:
        self.store = FakeWorkflowRunStateStore()
        self.reader = FakeWorkflowRunDeclarationReader()
        self.sink = FakeWorkflowEventSink()
        self.notifier = FakeWorkflowStatusNotifier()
        self.node_notifier = FakeWorkflowNodeStatusNotifier()
        self.agent_runs = FakeAgentRunReader()
        self.agent_runs.add_version(_AGENT, None)
        self.launcher = FakeAgentRunLauncher(self.store)
        self.advance = AdvanceWorkflowRunUseCase(
            self.store,
            self.reader,
            self.sink,
            self.notifier,
            FakeWorkflowClock(),
            agent_runs=self.agent_runs,
            approvals=FakeApprovalReader(),
            launcher=self.launcher,
            owner="worker-a",
            lease_ttl_seconds=60.0,
            node_notifier=self.node_notifier if with_node_notifier else None,
        )

    def declare_agent(self) -> UUID:
        return self.reader.add(
            (
                Node("start", NodeKind.START),
                Node("a", NodeKind.AGENT, agent_id=_AGENT),
                Node("end", NodeKind.END),
            ),
            (Edge("start", "a"), Edge("a", "end")),
            requested_by=UUID("00000000-0000-0000-0000-0000000000b1"),
        )

    def child_id(self, run_id: UUID) -> UUID:
        record = next(r for r in self.store.node_executions(run_id) if r.node_id == "a")
        assert record.agent_run_id is not None
        return record.agent_run_id


def _summary(m: WorkflowNodeStatusMessage) -> tuple[str, str, int]:
    return (m.node_id, m.status.value, m.status_seq)


def test_every_node_state_change_is_announced_with_the_event_seq() -> None:
    """`START → END`: 노드마다 시작과 마침 두 통지. `status_seq` 는 `node.started`·`node.finished`
    이벤트의 `seq` 와 같다(2, 3, 4, 5)."""
    rig = _Rig()
    run_id = rig.reader.add(*start_end_graph())

    rig.advance(run_id)

    assert [_summary(m) for m in rig.node_notifier.messages] == [
        ("start", "running", 2),
        ("start", "succeeded", 3),
        ("end", "running", 4),
        ("end", "succeeded", 5),
    ]
    node_event_seqs = [e.seq for e in rig.sink.events if e.type.startswith("node.")]
    assert [m.status_seq for m in rig.node_notifier.messages] == node_event_seqs
    assert [m.kind for m in rig.node_notifier.messages] == [
        NodeKind.START,
        NodeKind.START,
        NodeKind.END,
        NodeKind.END,
    ]
    assert all(m.workflow_run_id == run_id for m in rig.node_notifier.messages)


def test_start_carries_started_at_and_finish_carries_finished_at() -> None:
    rig = _Rig()
    run_id = rig.reader.add(*start_end_graph())

    rig.advance(run_id)

    started, finished = rig.node_notifier.messages[:2]
    assert started.started_at is not None and started.finished_at is None
    assert finished.finished_at is not None and finished.failure_reason is None


def test_parking_an_agent_node_announces_waiting_run_with_a_higher_seq() -> None:
    """파킹: `waiting_run` 통지의 `status_seq` 는 같은 노드의 시작 통지보다 크다(= `workflow.status`
    파킹 이벤트의 `seq`)."""
    rig = _Rig()
    run_id = rig.declare_agent()

    assert rig.advance(run_id) is WorkflowRunStatus.WAITING_RUN

    assert [_summary(m) for m in rig.node_notifier.messages if m.node_id == "a"] == [
        ("a", "running", 4),
        ("a", "waiting_run", 5),
    ]
    assert rig.notifier.messages[-1].seq == 5
    assert rig.node_notifier.messages[-1].finished_at is None


def test_a_failed_child_announces_the_node_failure_with_its_reason() -> None:
    """자식 Run 실패: 노드 `failed` 통지에 사유(`agent_run_failed`)와 마친 시각이 실린다."""
    rig = _Rig()
    run_id = rig.declare_agent()
    rig.advance(run_id)
    rig.agent_runs.set_status(rig.child_id(run_id), RunStatus.FAILED)

    rig.advance(run_id)

    failed = [m for m in rig.node_notifier.messages if m.status is NodeExecutionStatus.FAILED]
    assert [(m.node_id, m.failure_reason) for m in failed] == [
        ("a", WorkflowFailureReason.AGENT_RUN_FAILED)
    ]
    assert failed[0].finished_at is not None
    seqs = [m.status_seq for m in rig.node_notifier.messages if m.node_id == "a"]
    assert seqs == sorted(seqs) and len(set(seqs)) == len(seqs), "노드 키 안에서 엄격히 단조"


def test_the_message_has_no_node_output() -> None:
    """D-4: 출력은 통지 계약에 없다 -- `data` 평면에 머문다."""
    assert "output" not in WorkflowNodeStatusMessage.model_fields
    assert not any("output" in name for name in WorkflowNodeStatusMessage.model_fields)


def test_without_a_node_notifier_the_executor_behaves_as_before() -> None:
    rig = _Rig(with_node_notifier=False)
    run_id = rig.reader.add(*start_end_graph())

    assert rig.advance(run_id) is WorkflowRunStatus.SUCCEEDED
    assert rig.node_notifier.messages == []
