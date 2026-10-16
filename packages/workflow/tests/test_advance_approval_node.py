"""spec 0005 2.5, 2.6 개정 5, R-4, R-7, R-8, R-12, R-13, D-13 (P4-4): `AdvanceWorkflowRunUseCase` 의
`HUMAN`/`APPROVAL` 노드와 승인 대기 파킹 -- fake 포트로, 컨테이너 없이(AR-9).

증명하는 것: 두 종류가 **같게** `waiting_approval` 로 파킹된다 / 파킹하면 lease 를 놓고 기다리는
노드
실행의 id 를 상태에 남긴다 / **저장된 승인이 없으면** 재큐를 몇 번 받아도 아무 것도 바꾸지 않는다
(이벤트·`seq`·통지 증가 없음) / 다른 노드 실행의 승인은 근거가 아니다 / 승인이 저장되면 한 번만
전진한다 / 이벤트 payload 에 승인 주체가 실리지 않는다.

여기에 **권한 판정은 없습니다** -- 어느 테스트도 "누가 승인했는가" 를 묻지 않고, 실행기는 승인
주체를 읽지도 않습니다(`Approval` 에 `approved_by` 가 없다).
"""

from __future__ import annotations

from uuid import UUID

import pytest
from aether_workflow.application.usecases.advance_workflow_run import AdvanceWorkflowRunUseCase
from aether_workflow.domain.approval import Approval
from aether_workflow.domain.events import (
    PAYLOAD_MODELS,
    ApprovalGrantedPayload,
    ApprovalRequestedPayload,
)
from aether_workflow.domain.node import Edge, Node, NodeKind
from aether_workflow.domain.node_execution import NodeExecutionStatus
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

_OWNER = "worker-a"
_AGENT = UUID("00000000-0000-0000-0000-0000000000a1")
_APPROVAL_KINDS = [NodeKind.HUMAN, NodeKind.APPROVAL]


class _Rig:
    def __init__(self, *, sink: FakeWorkflowEventSink | None = None) -> None:
        self.store = FakeWorkflowRunStateStore()
        self.reader = FakeWorkflowRunDeclarationReader()
        self.sink = sink if sink is not None else FakeWorkflowEventSink()
        self.notifier = FakeWorkflowStatusNotifier()
        self.agent_runs = FakeAgentRunReader()
        self.agent_runs.add_version(_AGENT, None)
        self.approvals = FakeApprovalReader()
        self.launcher = FakeAgentRunLauncher(self.store)
        self.advance = AdvanceWorkflowRunUseCase(
            self.store,
            self.reader,
            self.sink,
            self.notifier,
            FakeWorkflowClock(),
            agent_runs=self.agent_runs,
            approvals=self.approvals,
            launcher=self.launcher,
            owner=_OWNER,
            lease_ttl_seconds=60.0,
        )

    def declare(self, kind: NodeKind, *, then_agent: bool = False) -> UUID:
        ids = ["start", "gate", *(["a"] if then_agent else []), "end"]
        nodes = (
            Node("start", NodeKind.START),
            Node("gate", kind),
            *([Node("a", NodeKind.AGENT, agent_id=_AGENT)] if then_agent else []),
            Node("end", NodeKind.END),
        )
        edges = tuple(Edge(a, b) for a, b in zip(ids, ids[1:], strict=False))
        return self.reader.add(nodes, edges)

    def types(self) -> list[str]:
        return [e.type for e in self.sink.events]

    def waiting_record_id(self, run_id: UUID) -> UUID:
        (record,) = [
            r
            for r in self.store.node_executions(run_id)
            if r.status is NodeExecutionStatus.WAITING_APPROVAL
        ]
        return record.id


@pytest.mark.parametrize("kind", _APPROVAL_KINDS)
def test_a_human_or_approval_node_parks_the_run_in_waiting_approval(kind: NodeKind) -> None:
    """spec 2.6 개정 5 (5): 두 종류를 **같게** 다룬다. 파킹하면 Workflow Run 은 `waiting_approval`,
    노드 실행은 `waiting_approval`, 기다리는 노드 실행의 id 가 상태와 통지에 남는다(R-12 의 지목
    대상)."""
    rig = _Rig()
    run_id = rig.declare(kind)

    result = rig.advance(run_id)

    assert result is WorkflowRunStatus.WAITING_APPROVAL
    execution = rig.store.executions[run_id]
    assert execution.status is WorkflowRunStatus.WAITING_APPROVAL
    assert execution.current_node_id == "gate"
    waiting_id = rig.waiting_record_id(run_id)
    assert execution.waiting_node_execution_id == waiting_id
    assert execution.waiting_run_id is None
    parked = rig.notifier.messages[-1]
    assert parked.status is WorkflowRunStatus.WAITING_APPROVAL
    assert parked.waiting_node_execution_id == waiting_id
    assert parked.waiting_run_id is None
    assert rig.types() == [
        "workflow.status",  # running
        "node.started",  # start
        "node.finished",
        "node.started",  # gate
        "workflow.status",  # waiting_approval
        "approval.requested",
    ]
    assert [r.node_id for r in rig.store.node_executions(run_id)] == ["start", "gate"]


def test_parking_releases_the_lease_so_a_waiting_run_holds_no_slot() -> None:
    """R-7: 승인을 기다리는 동안 lease 를 쥐지 않는다 -- 쥐고 있으면 worker 슬롯을 점유한다."""
    rig = _Rig()
    run_id = rig.declare(NodeKind.HUMAN)

    rig.advance(run_id)

    assert rig.store.lease_owner[run_id] is None
    # 파킹이 발행 앞에서 한 번, `finally` 가 한 번 더 놓는다(개정 8 (2) - 같은 owner 조건부 UPDATE
    # 라
    # 두 번째는 무해). 이 owner 만이 놓았다는 것이 판정이다.
    assert set(rig.store.released) == {(run_id, _OWNER)}


def test_a_failure_while_announcing_the_wait_still_releases_the_lease() -> None:
    """R-7: 파킹 중 예외가 나도 lease 는 `finally` 에서 놓인다 -- 대기하는 Run 이 락을 쥔 채
    남지 않는다."""
    rig = _Rig(sink=FakeWorkflowEventSink(fail_on="approval.requested"))
    run_id = rig.declare(NodeKind.HUMAN)

    with pytest.raises(ConnectionError):
        rig.advance(run_id)

    assert rig.store.lease_owner[run_id] is None


@pytest.mark.parametrize("requeues", [1, 2, 5])
def test_a_requeue_without_a_stored_approval_changes_nothing(requeues: int) -> None:
    """R-12, R-8: 재큐 메시지는 승인이 아니다. 저장된 승인이 없으면 몇 번을 받아도 상태·`seq`·
    이벤트·통지·노드 실행이 그대로다."""
    rig = _Rig()
    run_id = rig.declare(NodeKind.HUMAN)
    rig.advance(run_id)
    events = len(rig.sink.events)
    messages = len(rig.notifier.messages)
    status_calls = len(rig.store.set_status_calls)
    seq = rig.store.executions[run_id].status_seq
    records = rig.store.node_executions(run_id)

    for _ in range(requeues):
        assert rig.advance(run_id) is WorkflowRunStatus.WAITING_APPROVAL

    assert len(rig.sink.events) == events
    assert len(rig.notifier.messages) == messages
    assert len(rig.store.set_status_calls) == status_calls
    assert rig.store.executions[run_id].status_seq == seq
    assert rig.store.node_executions(run_id) == records
    assert rig.store.lease_owner[run_id] is None


def test_the_executor_asks_for_the_approval_of_the_awaited_node_execution() -> None:
    """spec 2.6 개정 5 (3): 전진의 근거는 **저장된 승인** 이다. 실행기는 기다리는 그 노드 실행의
    승인을 묻는다."""
    rig = _Rig()
    run_id = rig.declare(NodeKind.HUMAN)
    rig.advance(run_id)
    waiting_id = rig.waiting_record_id(run_id)

    rig.advance(run_id)

    assert rig.approvals.lookups
    assert set(rig.approvals.lookups) == {waiting_id}


def test_an_approval_for_another_node_execution_does_not_advance_the_run() -> None:
    """R-12: 다른 노드 실행에 대한 승인은 이 대기의 근거가 아니다."""
    rig = _Rig()
    run_id = rig.declare(NodeKind.HUMAN)
    rig.advance(run_id)
    rig.approvals.grant(UUID("00000000-0000-0000-0000-00000000dead"))

    assert rig.advance(run_id) is WorkflowRunStatus.WAITING_APPROVAL
    assert rig.store.executions[run_id].status is WorkflowRunStatus.WAITING_APPROVAL


@pytest.mark.parametrize("kind", _APPROVAL_KINDS)
def test_a_stored_approval_lets_the_run_advance_to_the_end(kind: NodeKind) -> None:
    """R-4, R-12: 승인이 저장되면 재개되어 END 에 닿는다. 노드 실행 기록이 순서대로 남고, 이벤트는
    `approval.granted` 가 `node.finished` 앞에 온다."""
    rig = _Rig()
    run_id = rig.declare(kind)
    rig.advance(run_id)
    rig.approvals.grant(rig.waiting_record_id(run_id))

    result = rig.advance(run_id)

    assert result is WorkflowRunStatus.SUCCEEDED
    records = rig.store.node_executions(run_id)
    assert [(r.node_id, r.status) for r in records] == [
        ("start", NodeExecutionStatus.SUCCEEDED),
        ("gate", NodeExecutionStatus.SUCCEEDED),
        ("end", NodeExecutionStatus.SUCCEEDED),
    ]
    types = rig.types()
    assert types.count("approval.requested") == 1
    assert types.count("approval.granted") == 1
    granted_at = types.index("approval.granted")
    assert types[granted_at + 1] == "node.finished"
    assert types[-2:] == ["workflow.status", "workflow.finished"]
    execution = rig.store.executions[run_id]
    assert execution.waiting_node_execution_id is None, "대기가 끝나면 지목 대상이 지워진다"


def test_the_same_approval_advances_only_once_however_often_the_run_is_requeued() -> None:
    """R-8: 승인이 저장된 뒤 재큐가 여러 번 와도 노드는 한 번만 전진한다 -- 이벤트도 한 번씩."""
    rig = _Rig()
    run_id = rig.declare(NodeKind.HUMAN)
    rig.advance(run_id)
    rig.approvals.grant(rig.waiting_record_id(run_id))

    for _ in range(3):
        rig.advance(run_id)

    assert rig.types().count("approval.granted") == 1
    assert rig.types().count("workflow.finished") == 1
    assert [r.node_id for r in rig.store.node_executions(run_id)] == ["start", "gate", "end"]


def test_after_the_approval_the_run_continues_into_the_next_parking_node() -> None:
    """R-4(일부): 승인 뒤 다음 노드(AGENT)로 가서 이번엔 `waiting_run` 으로 파킹한다 -- 두 대기가
    **상태만으로** 구별된다(R-13): `waiting_node_execution_id` 는 지워지고 `waiting_run_id` 가
    선다."""
    rig = _Rig()
    run_id = rig.declare(NodeKind.HUMAN, then_agent=True)
    rig.advance(run_id)
    rig.approvals.grant(rig.waiting_record_id(run_id))

    result = rig.advance(run_id)

    assert result is WorkflowRunStatus.WAITING_RUN
    execution = rig.store.executions[run_id]
    assert execution.status is WorkflowRunStatus.WAITING_RUN
    assert execution.waiting_run_id is not None
    assert execution.waiting_node_execution_id is None
    assert len(rig.launcher.launches) == 1


def test_a_crash_between_marking_the_node_and_the_run_parks_again_without_a_second_node() -> None:
    """R-6, R-8: 노드 실행을 `waiting_approval` 로 바꾼 뒤 Workflow Run 의 상태를 저장하기 전에
    죽었다. 재전달은 새 노드 실행 행을 만들지 않고 같은 행을 기다린다."""
    rig = _Rig()
    run_id = rig.declare(NodeKind.HUMAN)
    rig.store.seed(run_id, status=WorkflowRunStatus.RUNNING, status_seq=3, current_node_id="gate")
    start = rig.store.start_node(run_id, "start", 0)
    assert start is not None
    rig.store.finish_node(start, NodeExecutionStatus.SUCCEEDED, FakeWorkflowClock().now())
    gate = rig.store.start_node(run_id, "gate", 0)
    assert gate is not None
    rig.store.park_node_for_approval(gate)

    result = rig.advance(run_id)

    assert result is WorkflowRunStatus.WAITING_APPROVAL
    assert [r.node_id for r in rig.store.node_executions(run_id)] == ["start", "gate"]
    assert rig.store.executions[run_id].waiting_node_execution_id == gate


def test_a_waiting_run_without_the_awaited_node_execution_stays_parked() -> None:
    """fail-closed: 상태가 `waiting_approval` 인데 무엇을 기다리는지 모르면(포인터 없음) 전진하지
    않는다. 승인을 증명할 수 없으면 멈춘다."""
    rig = _Rig()
    run_id = rig.declare(NodeKind.HUMAN)
    rig.store.seed(
        run_id, status=WorkflowRunStatus.WAITING_APPROVAL, status_seq=5, current_node_id="gate"
    )

    assert rig.advance(run_id) is WorkflowRunStatus.WAITING_APPROVAL
    assert rig.store.set_status_calls == []


def test_event_payloads_carry_the_node_and_never_the_approver() -> None:
    """spec 2.6 개정 5 (4), 보고 판단: 승인 주체의 id 를 이벤트 스트림에 싣지 않는다 -- 기록은
    `control` 에 있고 조회로 본다. 두 payload 는 `node_id`·`iteration` 만 갖는다."""
    assert ApprovalRequestedPayload(node_id="g", iteration=0).model_dump() == {
        "node_id": "g",
        "iteration": 0,
    }
    assert ApprovalGrantedPayload(node_id="g", iteration=0).model_dump() == {
        "node_id": "g",
        "iteration": 0,
    }
    assert PAYLOAD_MODELS["approval.requested"] is ApprovalRequestedPayload
    assert PAYLOAD_MODELS["approval.granted"] is ApprovalGrantedPayload

    rig = _Rig()
    run_id = rig.declare(NodeKind.HUMAN)
    rig.advance(run_id)
    rig.approvals.grant(rig.waiting_record_id(run_id))
    rig.advance(run_id)
    approval_events = [e for e in rig.sink.events if e.type.startswith("approval.")]
    assert [e.type for e in approval_events] == ["approval.requested", "approval.granted"]
    for event in approval_events:
        assert event.payload == {"node_id": "gate", "iteration": 0}


def test_the_approval_value_object_has_no_approver() -> None:
    """spec 2.6 / C-4: 실행기가 읽는 `Approval` 은 승인 주체를 갖지 않는다 -- 실행기는 누가
    승인했는지 모르고 물을 수도 없다(권한 판정의 자리가 없다)."""
    assert set(Approval.__dataclass_fields__) == {"node_execution_id", "approved_at"}
