"""spec 0005 2.3, 2.9 개정 2, 2.10, R-6, R-8, D-13: `AdvanceWorkflowRunUseCase` — 실행기 골격
(`START` → `END`)의 계약. fake 저장소·sink·clock 으로 컨테이너 없이 돕니다(AR-9).
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from aether_workflow.application.ports.inbound.advance_workflow_run import WorkflowLeaseHeld
from aether_workflow.application.usecases.advance_workflow_run import AdvanceWorkflowRunUseCase
from aether_workflow.domain.failure import WorkflowFailureReason
from aether_workflow.domain.node import Edge, Node, NodeKind
from aether_workflow.domain.node_execution import NodeExecutionStatus
from aether_workflow.domain.run_status import IllegalWorkflowTransition, WorkflowRunStatus

from packages.workflow.tests.fakes import (
    FakeAgentRunLauncher,
    FakeAgentRunReader,
    FakeApprovalReader,
    FakeWorkflowClock,
    FakeWorkflowEventSink,
    FakeWorkflowRunDeclarationReader,
    FakeWorkflowRunStateStore,
    FakeWorkflowStatusNotifier,
    start_end_graph,
)

_OWNER = "worker-a"


class _Rig:
    def __init__(self, *, sink: FakeWorkflowEventSink | None = None) -> None:
        self.store = FakeWorkflowRunStateStore()
        self.reader = FakeWorkflowRunDeclarationReader()
        self.sink = sink or FakeWorkflowEventSink()
        self.notifier = FakeWorkflowStatusNotifier()
        self.agent_runs = FakeAgentRunReader()
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
            owner=_OWNER,
            lease_ttl_seconds=60.0,
        )

    def types(self) -> list[str]:
        return [e.type for e in self.sink.events]


def test_start_to_end_succeeds_and_persists_the_terminal_state() -> None:
    """spec 0005 2.3: `START` → `END` Workflow 는 `succeeded` 로 끝나고 시각이 남는다."""
    rig = _Rig()
    run_id = rig.reader.add(*start_end_graph())

    status = rig.advance(run_id)

    assert status is WorkflowRunStatus.SUCCEEDED
    execution = rig.store.load(run_id)
    assert execution is not None
    assert execution.status is WorkflowRunStatus.SUCCEEDED
    assert execution.started_at is not None
    assert execution.finished_at is not None
    assert execution.current_node_id == "end"


def test_both_nodes_are_recorded_exactly_once_and_succeeded() -> None:
    """spec 0005 2.9: 노드 실행 기록 둘(START, END), 둘 다 `succeeded`."""
    rig = _Rig()
    run_id = rig.reader.add(*start_end_graph())

    rig.advance(run_id)

    records = rig.store.node_executions(run_id)
    assert [(r.node_id, r.status) for r in records] == [
        ("start", NodeExecutionStatus.SUCCEEDED),
        ("end", NodeExecutionStatus.SUCCEEDED),
    ]
    assert all(r.finished_at is not None for r in records)


def test_events_use_the_four_workflow_types_in_order_with_monotonic_seq() -> None:
    """spec 0005 2.10, D-13: 네 종류, 순서, `seq` 는 1 부터 빈틈없이 단조 증가."""
    rig = _Rig()
    run_id = rig.reader.add(*start_end_graph())

    rig.advance(run_id)

    assert rig.types() == [
        "workflow.status",
        "node.started",
        "node.finished",
        "node.started",
        "node.finished",
        "workflow.status",
        "workflow.finished",
    ]
    assert [e.seq for e in rig.sink.events] == [1, 2, 3, 4, 5, 6, 7]
    assert all(e.workflow_run_id == run_id and e.v == 1 for e in rig.sink.events)
    assert rig.sink.events[0].payload == {"status": "running"}
    assert rig.sink.events[-2].payload["status"] == "succeeded"
    assert rig.sink.events[-1].payload == {"status": "succeeded"}


def test_status_notifications_share_the_event_sequence() -> None:
    """spec 0005 2.9 개정 2: 상태 통지는 `workflow.status` 이벤트와 같은 `seq` 수열을 쓴다."""
    rig = _Rig()
    run_id = rig.reader.add(*start_end_graph())

    rig.advance(run_id)

    status_event_seqs = [e.seq for e in rig.sink.events if e.type == "workflow.status"]
    assert [m.seq for m in rig.notifier.messages] == status_event_seqs == [1, 6]
    assert [m.status for m in rig.notifier.messages] == [
        WorkflowRunStatus.RUNNING,
        WorkflowRunStatus.SUCCEEDED,
    ]
    assert rig.notifier.messages[0].started_at is not None
    assert rig.notifier.messages[1].finished_at is not None
    assert rig.notifier.messages[1].current_node_id == "end"
    execution = rig.store.load(run_id)
    assert execution is not None
    assert execution.status_seq == 7


def test_a_terminal_run_is_not_advanced_again() -> None:
    """spec 0005 2.3: 종결 상태에서 다시 불러도 아무것도 하지 않고 그 상태를 돌려준다."""
    rig = _Rig()
    run_id = rig.reader.add(*start_end_graph())
    rig.advance(run_id)
    events_before = len(rig.sink.events)
    notifications_before = len(rig.notifier.messages)
    start_calls_before = len(rig.store.start_node_calls)

    status = rig.advance(run_id)

    assert status is WorkflowRunStatus.SUCCEEDED
    assert len(rig.sink.events) == events_before
    assert len(rig.notifier.messages) == notifications_before
    assert len(rig.store.start_node_calls) == start_calls_before
    assert rig.store.lease_owner[run_id] is None, "종결 상태를 본 호출도 lease 를 놓는다"


def test_a_finished_node_is_not_executed_again_on_resume() -> None:
    """spec 0005 R-6, R-8: 이미 마친 노드(`start_node` → None)는 다시 실행하지 않는다."""
    rig = _Rig()
    run_id = rig.reader.add(*start_end_graph())
    rig.store.seed(run_id, status=WorkflowRunStatus.RUNNING, status_seq=3, current_node_id="start")
    rig.store.seed_node(run_id, "start", NodeExecutionStatus.SUCCEEDED)

    status = rig.advance(run_id)

    assert status is WorkflowRunStatus.SUCCEEDED
    records = rig.store.node_executions(run_id)
    assert [r.node_id for r in records] == ["start", "end"], "START 기록은 한 행 그대로"
    started = [e.payload["node_id"] for e in rig.sink.events if e.type == "node.started"]
    assert started == ["end"], "마친 START 의 node.started 를 다시 내지 않는다"
    status_payloads = [e.payload["status"] for e in rig.sink.events if e.type == "workflow.status"]
    assert status_payloads == ["succeeded"], "이미 running 이면 running 전이를 다시 내지 않는다"


def test_a_node_left_running_by_a_crash_is_finished_not_restarted() -> None:
    """spec 0005 R-6: `running` 으로 남은 기록은 새 행 없이 마무리된다."""
    rig = _Rig()
    run_id = rig.reader.add(*start_end_graph())
    rig.store.seed(run_id, status=WorkflowRunStatus.RUNNING, status_seq=2, current_node_id="start")
    rig.store.seed_node(run_id, "start", NodeExecutionStatus.RUNNING)

    rig.advance(run_id)

    records = rig.store.node_executions(run_id)
    assert [(r.node_id, r.status) for r in records] == [
        ("start", NodeExecutionStatus.SUCCEEDED),
        ("end", NodeExecutionStatus.SUCCEEDED),
    ]


def test_seq_continues_from_the_persisted_status_seq() -> None:
    """spec 0005 2.9 개정 2: 정본은 `status_seq` — 재개해도 수열이 이어지고 되돌아가지 않는다."""
    rig = _Rig()
    run_id = rig.reader.add(*start_end_graph())
    rig.store.seed(run_id, status=WorkflowRunStatus.RUNNING, status_seq=10, current_node_id="start")
    rig.store.seed_node(run_id, "start", NodeExecutionStatus.SUCCEEDED)

    rig.advance(run_id)

    seqs = [e.seq for e in rig.sink.events]
    assert seqs[0] == 11
    assert seqs == list(range(11, 11 + len(seqs)))


def test_lease_held_by_another_owner_raises_and_touches_nothing() -> None:
    """spec 0005 2.1: 다른 owner 가 lease 를 쥐면 `WorkflowLeaseHeld` - 그의 lease 는 그대로."""
    rig = _Rig()
    run_id = rig.reader.add(*start_end_graph())
    rig.store.seed(run_id, status=WorkflowRunStatus.QUEUED)
    rig.store.hold(run_id, "worker-b")

    with pytest.raises(WorkflowLeaseHeld):
        rig.advance(run_id)

    assert rig.store.lease_owner[run_id] == "worker-b"
    assert rig.sink.events == []
    assert rig.notifier.messages == []
    assert rig.store.set_status_calls == []
    assert rig.store.released == [], "잡지 못한 lease 는 놓지도 않는다"


def test_missing_declaration_is_a_runtime_error_before_any_lease() -> None:
    """spec 0005 2.3: 선언이 없으면 `RuntimeError`(독약 메시지) - lease 도 잡지 않는다."""
    rig = _Rig()

    with pytest.raises(RuntimeError):
        rig.advance(uuid4())

    assert rig.store.executions == {}


def test_unsupported_node_kind_fails_with_a_distinct_reason_and_no_half_node() -> None:
    """plan 부록 A: 지원하지 않는 종류는 `failed` + 구별되는 사유, 절반만 만든 노드는 없다."""
    rig = _Rig()
    run_id = rig.reader.add(
        (Node("start", NodeKind.START), Node("a", NodeKind.LLM), Node("end", NodeKind.END)),
        (Edge("start", "a"), Edge("a", "end")),
    )

    status = rig.advance(run_id)

    assert status is WorkflowRunStatus.FAILED
    execution = rig.store.load(run_id)
    assert execution is not None
    assert execution.failure_reason == WorkflowFailureReason.UNSUPPORTED_NODE_KIND.value
    assert execution.current_node_id == "a"
    assert [r.node_id for r in rig.store.node_executions(run_id)] == ["start"]
    assert rig.types()[-2:] == ["workflow.status", "workflow.finished"]
    assert rig.sink.events[-2].payload == {
        "status": "failed",
        "current_node_id": "a",
        "failure_reason": "unsupported_node_kind",
    }
    assert rig.sink.events[-1].payload == {"status": "failed"}
    last = rig.notifier.messages[-1]
    assert last.status is WorkflowRunStatus.FAILED
    assert last.failure_reason is WorkflowFailureReason.UNSUPPORTED_NODE_KIND
    assert last.finished_at is not None


def test_more_than_one_outgoing_edge_fails_instead_of_picking_one() -> None:
    """plan 부록 A: 간선이 여러 개면 조용히 하나를 고르지 않는다(분기는 P4-2b)."""
    rig = _Rig()
    run_id = rig.reader.add(
        (Node("start", NodeKind.START), Node("x", NodeKind.END), Node("y", NodeKind.END)),
        (Edge("start", "x"), Edge("start", "y")),
    )

    status = rig.advance(run_id)

    assert status is WorkflowRunStatus.FAILED
    execution = rig.store.load(run_id)
    assert execution is not None
    assert execution.failure_reason == WorkflowFailureReason.UNSUPPORTED_BRANCHING.value
    assert [r.node_id for r in rig.store.node_executions(run_id)] == ["start"]


def test_a_node_without_outgoing_edge_fails_as_invalid_graph() -> None:
    """저장 시점 검증을 우회한 그래프도 멈추지 않고 `failed` 로 끝난다."""
    rig = _Rig()
    run_id = rig.reader.add((Node("start", NodeKind.START),), ())

    status = rig.advance(run_id)

    assert status is WorkflowRunStatus.FAILED
    execution = rig.store.load(run_id)
    assert execution is not None
    assert execution.failure_reason == WorkflowFailureReason.INVALID_GRAPH.value


def test_lease_is_released_on_success_and_on_exception() -> None:
    """plan 부록 A 8: 끝에서 `release` - 예외 경로에서도(`finally`)."""
    ok = _Rig()
    ok_id = ok.reader.add(*start_end_graph())
    ok.advance(ok_id)
    assert ok.store.released == [(ok_id, _OWNER)]
    assert ok.store.lease_owner[ok_id] is None

    boom = _Rig(sink=FakeWorkflowEventSink(fail_on="node.started"))
    boom_id = boom.reader.add(*start_end_graph())
    with pytest.raises(ConnectionError):
        boom.advance(boom_id)
    assert boom.store.released == [(boom_id, _OWNER)]
    assert boom.store.lease_owner[boom_id] is None


def test_a_transition_the_table_forbids_is_rejected_and_releases_the_lease(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """spec 0005 2.3: `queued → running` 은 `can_transition` 이 판정한다 - 어기면 거부."""
    monkeypatch.setattr(
        "aether_workflow.application.usecases.advance_workflow_run.can_transition",
        lambda source, target: False,
    )
    rig = _Rig()
    run_id = rig.reader.add(*start_end_graph())

    with pytest.raises(IllegalWorkflowTransition):
        rig.advance(run_id)

    assert rig.sink.events == []
    assert rig.store.released == [(run_id, _OWNER)]
