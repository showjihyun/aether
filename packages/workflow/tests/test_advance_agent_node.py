"""spec 0005 2.3, 2.5 개정 3, R-7, R-8, D-4 (P4-2a B2): `AdvanceWorkflowRunUseCase` 의 `AGENT`
노드와
파킹 -- fake 포트로, 컨테이너 없이(AR-9).

증명하는 것: 자식 Run 의 id 를 **영속한 뒤에** 발사한다 / 파킹하면 lease 를 놓고 `waiting_run` 과
기다리는 대상을 남긴다 / 같은 깨우는 신호가 두 번 와도 전진은 한 번 / 자식 종결 뒤 한 번 전진 /
자식이 실패하면 Workflow 가 `agent_run_failed` / 해석 실패와 요청자 없음은 구별되는 사유로 노드
실패.
"""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from aether_runtime.domain.run import RunStatus
from aether_workflow.application.usecases.advance_workflow_run import AdvanceWorkflowRunUseCase
from aether_workflow.domain.node import Edge, Node, NodeKind
from aether_workflow.domain.node_execution import NodeExecutionStatus
from aether_workflow.domain.run_status import WorkflowRunStatus

from packages.workflow.tests.fakes import (
    REQUESTER,
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


class _Rig:
    def __init__(self, *, launcher_failure: Exception | None = None) -> None:
        self.store = FakeWorkflowRunStateStore()
        self.reader = FakeWorkflowRunDeclarationReader()
        self.sink = FakeWorkflowEventSink()
        self.notifier = FakeWorkflowStatusNotifier()
        self.agent_runs = FakeAgentRunReader()
        self.launcher = FakeAgentRunLauncher(self.store, fail_with=launcher_failure)
        self.version = self.agent_runs.add_version(_AGENT, None)
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

    def declare(
        self,
        *,
        agent_nodes: tuple[str, ...] = ("a",),
        input: dict[str, object] | None = None,
        requested_by: UUID | None = REQUESTER,
        agent_id: UUID | None = _AGENT,
        agent_version: int | None = None,
    ) -> UUID:
        ids = ["start", *agent_nodes, "end"]
        nodes = (
            Node("start", NodeKind.START),
            *(
                Node(n, NodeKind.AGENT, agent_id=agent_id, agent_version=agent_version)
                for n in agent_nodes
            ),
            Node("end", NodeKind.END),
        )
        edges = tuple(Edge(a, b) for a, b in zip(ids, ids[1:], strict=False))
        return self.reader.add(nodes, edges, input=input, requested_by=requested_by)

    def types(self) -> list[str]:
        return [e.type for e in self.sink.events]

    def child_id(self, run_id: UUID, node_id: str = "a") -> UUID:
        record = next(r for r in self.store.node_executions(run_id) if r.node_id == node_id)
        assert record.agent_run_id is not None
        return record.agent_run_id

    def execution(self, run_id: UUID):  # type: ignore[no-untyped-def]
        execution = self.store.load(run_id)
        assert execution is not None
        return execution


def test_first_pass_launches_the_child_and_parks_the_workflow() -> None:
    """spec 0005 2.5: `START → AGENT` 에서 자식을 발사하고 `waiting_run` 으로 파킹한다 -- 상태와
    기다리는 대상이 남고(R-13) 노드는 `waiting_run`, 이벤트·통지는 같은 seq 수열."""
    rig = _Rig()
    run_id = rig.declare(input={"q": "안녕"})

    status = rig.advance(run_id)

    assert status is WorkflowRunStatus.WAITING_RUN
    child = rig.child_id(run_id)
    execution = rig.execution(run_id)
    assert (execution.status, execution.current_node_id, execution.waiting_run_id) == (
        WorkflowRunStatus.WAITING_RUN,
        "a",
        child,
    )
    assert [(r.node_id, r.status) for r in rig.store.node_executions(run_id)] == [
        ("start", NodeExecutionStatus.SUCCEEDED),
        ("a", NodeExecutionStatus.WAITING_RUN),
    ]
    assert rig.types() == [
        "workflow.status",
        "node.started",
        "node.finished",
        "node.started",
        "workflow.status",
    ]
    assert [e.seq for e in rig.sink.events] == [1, 2, 3, 4, 5]
    assert rig.sink.events[-1].payload == {"status": "waiting_run", "current_node_id": "a"}
    last = rig.notifier.messages[-1]
    assert (last.status, last.seq, last.waiting_run_id, last.current_node_id) == (
        WorkflowRunStatus.WAITING_RUN,
        5,
        child,
        "a",
    )
    assert execution.status_seq == 5


def test_launch_request_carries_the_resolved_version_requester_and_serialized_input() -> None:
    """spec 0005 2.5 개정 3: 입력은 Workflow Run 의 `input` 직렬화, 요청자는 Workflow 를 시작한
    주체, Version 은 실행기가 해석한 id."""
    rig = _Rig()
    run_id = rig.declare(input={"b": 2, "a": "안녕"})

    rig.advance(run_id)

    (launch,) = rig.launcher.launches
    assert launch.agent_run_id == rig.child_id(run_id)
    assert launch.agent_version_id == rig.version.agent_version_id
    assert launch.requested_by == REQUESTER
    assert launch.input == '{"a":"안녕","b":2}', "정렬된 compact JSON, 한글은 이스케이프하지 않는다"
    assert rig.agent_runs.version_lookups == [(_AGENT, None)]


def test_missing_workflow_input_is_sent_as_an_empty_string() -> None:
    rig = _Rig()
    run_id = rig.declare(input=None)

    rig.advance(run_id)

    assert rig.launcher.launches[0].input == ""


def test_pinned_agent_version_is_resolved_with_that_number() -> None:
    rig = _Rig()
    rig.agent_runs.add_version(_AGENT, 3)
    run_id = rig.declare(agent_version=3)

    rig.advance(run_id)

    assert rig.agent_runs.version_lookups == [(_AGENT, 3)]


def test_child_id_is_persisted_before_the_launch() -> None:
    """spec 0005 R-8: id 를 영속한 **뒤에** 발사한다. 순서가 반대면 재전달에서 id 를 다시 만들어
    자식 Run 이 둘이 된다 -- 발사하는 순간 저장소에 같은 id 가 이미 있어야 한다."""
    rig = _Rig()
    run_id = rig.declare()

    rig.advance(run_id)

    assert rig.launcher.persisted_at_launch == [True]
    assert [name for name, _ in rig.store.events_log] == ["park_node", "launch"]


def test_parking_releases_the_lease() -> None:
    """spec 0005 R-7: 대기 중에 lease 를 쥐고 있으면 worker 슬롯을 점유한다 -- 파킹한 호출도
    `finally` 에서 lease 를 놓는다."""
    rig = _Rig()
    run_id = rig.declare()

    rig.advance(run_id)

    assert rig.store.lease_owner[run_id] is None
    # 파킹이 발행 앞에서 한 번, `finally` 가 한 번 더 놓는다(개정 8 (2) - 같은 owner 조건부 UPDATE
    # 라
    # 두 번째는 무해). 이 owner 만이 놓았다는 것이 판정이다.
    assert set(rig.store.released) == {(run_id, _OWNER)}


def test_a_wake_signal_while_the_child_is_not_finished_changes_nothing() -> None:
    """spec 0005 R-8: 깨우는 신호가 와도 자식이 아직 종결이 아니면 파킹을 유지한다 -- 새 이벤트·새
    통지·`seq` 증가·새 발사가 없고 lease 는 놓는다. 몇 번을 와도 같다."""
    rig = _Rig()
    run_id = rig.declare()
    rig.advance(run_id)
    child = rig.child_id(run_id)
    rig.agent_runs.set_status(child, RunStatus.RUNNING)
    events, messages = len(rig.sink.events), len(rig.notifier.messages)
    status_calls = list(rig.store.set_status_calls)

    results = [rig.advance(run_id) for _ in range(3)]

    assert results == [WorkflowRunStatus.WAITING_RUN] * 3
    assert len(rig.sink.events) == events
    assert len(rig.notifier.messages) == messages
    assert rig.store.set_status_calls == status_calls, "저장도 하지 않는다(seq 증가 없음)"
    assert len(rig.launcher.launches) == 1
    assert len(rig.store.node_executions(run_id)) == 2
    assert rig.execution(run_id).status_seq == 5
    assert rig.store.lease_owner[run_id] is None


def test_a_wake_before_the_child_row_exists_also_keeps_the_park() -> None:
    """자식이 아직 worker 에게 집히지 않아 실행 행이 없는(`None`) 상태도 "종결 아님" 이다 -- 다시
    발사하지 않는다(이미 `waiting_run` 으로 파킹했다는 것은 발사가 끝났다는 뜻)."""
    rig = _Rig()
    run_id = rig.declare()
    rig.advance(run_id)

    status = rig.advance(run_id)

    assert status is WorkflowRunStatus.WAITING_RUN
    assert len(rig.launcher.launches) == 1


def test_child_succeeded_advances_once_to_the_end() -> None:
    """spec 0005 R-8: 자식이 종결이면 노드를 마치고 다음 노드로 -- 전진은 한 번이고 `END` 에서
    `succeeded`. `waiting_run_id` 는 지워진다."""
    rig = _Rig()
    run_id = rig.declare()
    rig.advance(run_id)
    rig.agent_runs.set_status(rig.child_id(run_id), RunStatus.SUCCEEDED)

    status = rig.advance(run_id)

    assert status is WorkflowRunStatus.SUCCEEDED
    assert [(r.node_id, r.status) for r in rig.store.node_executions(run_id)] == [
        ("start", NodeExecutionStatus.SUCCEEDED),
        ("a", NodeExecutionStatus.SUCCEEDED),
        ("end", NodeExecutionStatus.SUCCEEDED),
    ]
    execution = rig.execution(run_id)
    assert execution.waiting_run_id is None
    assert execution.current_node_id == "end"
    assert rig.types()[5:] == [
        "workflow.status",  # waiting_run -> running
        "node.finished",
        "node.started",
        "node.finished",
        "workflow.status",
        "workflow.finished",
    ]
    seqs = [e.seq for e in rig.sink.events]
    assert seqs == list(range(1, len(seqs) + 1))
    assert rig.sink.events[5].payload == {"status": "running"}
    assert len(rig.launcher.launches) == 1


def test_the_same_wake_signal_twice_advances_exactly_once() -> None:
    """spec 0005 R-8 의 핵심: 같은 신호가 두 번 와도 노드는 한 번만 전진한다. 두 번째는 종결 상태를
    보고 아무 것도 하지 않는다."""
    rig = _Rig()
    run_id = rig.declare()
    rig.advance(run_id)
    rig.agent_runs.set_status(rig.child_id(run_id), RunStatus.SUCCEEDED)

    first = rig.advance(run_id)
    events, messages, nodes = (
        len(rig.sink.events),
        len(rig.notifier.messages),
        len(rig.store.node_executions(run_id)),
    )
    second = rig.advance(run_id)

    assert (first, second) == (WorkflowRunStatus.SUCCEEDED, WorkflowRunStatus.SUCCEEDED)
    assert len(rig.sink.events) == events
    assert len(rig.notifier.messages) == messages
    assert len(rig.store.node_executions(run_id)) == nodes == 3
    assert len(rig.launcher.launches) == 1


@pytest.mark.parametrize("terminal", [RunStatus.FAILED, RunStatus.CANCELLED, RunStatus.TIMED_OUT])
def test_a_child_that_did_not_succeed_fails_the_workflow(terminal: RunStatus) -> None:
    """spec 0005 2.3: 자식 Run 이 `succeeded` 가 아닌 종결이면 Workflow Run 은 `failed` +
    `agent_run_failed` 이고 노드도 `failed`. `END` 에 닿지 않는다."""
    rig = _Rig()
    run_id = rig.declare()
    rig.advance(run_id)
    rig.agent_runs.set_status(rig.child_id(run_id), terminal)

    status = rig.advance(run_id)

    assert status is WorkflowRunStatus.FAILED
    execution = rig.execution(run_id)
    assert (execution.failure_reason, execution.current_node_id) == ("agent_run_failed", "a")
    records = rig.store.node_executions(run_id)
    assert [(r.node_id, r.status) for r in records] == [
        ("start", NodeExecutionStatus.SUCCEEDED),
        ("a", NodeExecutionStatus.FAILED),
    ]
    assert records[1].failure_reason == "agent_run_failed"
    assert rig.sink.events[-2].payload == {
        "status": "failed",
        "current_node_id": "a",
        "failure_reason": "agent_run_failed",
    }
    assert rig.types()[-1] == "workflow.finished"
    assert rig.notifier.messages[-1].status is WorkflowRunStatus.FAILED


def test_an_unresolvable_agent_fails_the_node_without_launching() -> None:
    """plan 부록 A: 없는 Agent 를 가리킨 노드는 **영원히 파킹되지 않는다** -- 발사 없이 노드 실패 +
    구별되는 사유 `agent_version_not_found`."""
    rig = _Rig()
    run_id = rig.declare(agent_id=uuid4())

    status = rig.advance(run_id)

    assert status is WorkflowRunStatus.FAILED
    assert rig.execution(run_id).failure_reason == "agent_version_not_found"
    assert rig.launcher.launches == []
    assert rig.agent_runs.version_lookups != []
    (_, node_record) = rig.store.node_executions(run_id)
    assert node_record.status is NodeExecutionStatus.FAILED
    assert node_record.agent_run_id is None, "발사하지 않았으니 자식 id 도 만들지 않는다"
    assert rig.types()[-1] == "workflow.finished"


def test_an_agent_node_without_reference_is_failed_not_launched() -> None:
    """저장 때 거부되는 모양이지만(spec 2.2 개정 3) 옛 행에는 있을 수 있다 -- 조용히 넘기지 않고
    `agent_version_not_found` 로 실패시킨다."""
    rig = _Rig()
    run_id = rig.declare(agent_id=None)

    status = rig.advance(run_id)

    assert status is WorkflowRunStatus.FAILED
    assert rig.execution(run_id).failure_reason == "agent_version_not_found"
    assert rig.launcher.launches == []
    assert rig.agent_runs.version_lookups == []


def test_a_pinned_version_that_does_not_exist_fails_the_node() -> None:
    rig = _Rig()
    run_id = rig.declare(agent_version=9)

    status = rig.advance(run_id)

    assert status is WorkflowRunStatus.FAILED
    assert rig.execution(run_id).failure_reason == "agent_version_not_found"


def test_a_workflow_run_without_requester_fails_the_node_without_launching() -> None:
    """0007 이전에 만들어진 행은 요청자를 모른다. 비운 채로 발사하면 자식 Run 의 조회가 500 이므로
    조용히 넘기지 않고 `workflow_run_without_requester` 로 노드를 실패시킨다."""
    rig = _Rig()
    run_id = rig.declare(requested_by=None)

    status = rig.advance(run_id)

    assert status is WorkflowRunStatus.FAILED
    assert rig.execution(run_id).failure_reason == "workflow_run_without_requester"
    assert rig.launcher.launches == []
    assert rig.store.lease_owner[run_id] is None


def test_a_terminal_workflow_is_never_reentered_by_a_late_wake() -> None:
    """종결 상태에서 재진입 금지 -- 늦게 온 신호가 자식을 다시 발사하거나 노드를 늘리지 않는다."""
    rig = _Rig()
    run_id = rig.declare(agent_id=uuid4())
    rig.advance(run_id)
    lookups = len(rig.agent_runs.version_lookups)
    nodes = len(rig.store.node_executions(run_id))

    status = rig.advance(run_id)

    assert status is WorkflowRunStatus.FAILED
    assert rig.launcher.launches == []
    assert len(rig.agent_runs.version_lookups) == lookups
    assert len(rig.store.node_executions(run_id)) == nodes


def test_a_launch_failure_keeps_the_persisted_id_and_the_retry_reuses_it() -> None:
    """발사가 실패하면(Redis 장애) 예외가 올라가고 lease 는 놓인다. id 는 이미 영속돼 있으므로
    재전달은 **같은 id** 로 다시 발사한다 -- 자식 Run 이 둘이 되지 않는다(R-8)."""
    rig = _Rig(launcher_failure=ConnectionError("redis down"))
    run_id = rig.declare()

    with pytest.raises(ConnectionError):
        rig.advance(run_id)

    persisted = rig.child_id(run_id)
    assert rig.store.lease_owner[run_id] is None
    assert rig.execution(run_id).status is WorkflowRunStatus.RUNNING, "파킹하지 못했다"

    healthy = FakeAgentRunLauncher(rig.store)
    retry = AdvanceWorkflowRunUseCase(
        rig.store,
        rig.reader,
        rig.sink,
        rig.notifier,
        FakeWorkflowClock(),
        agent_runs=rig.agent_runs,
        approvals=FakeApprovalReader(),
        launcher=healthy,
        owner=_OWNER,
        lease_ttl_seconds=60.0,
    )
    status = retry(run_id)

    assert status is WorkflowRunStatus.WAITING_RUN
    assert [launch.agent_run_id for launch in healthy.launches] == [persisted]
    assert len(rig.store.node_executions(run_id)) == 2, "노드 실행 기록은 노드당 한 행"


def test_a_node_left_running_without_a_child_id_is_launched_once_with_a_new_id() -> None:
    """노드 행을 만들고 id 를 영속하기 전에 죽었다 -- 새 행 없이 이어서 id 를 정하고 발사한다."""
    rig = _Rig()
    run_id = rig.declare()
    rig.store.seed(run_id, status=WorkflowRunStatus.RUNNING, status_seq=3, current_node_id="start")
    rig.store.seed_node(run_id, "start", NodeExecutionStatus.SUCCEEDED)
    rig.store.seed_node(run_id, "a", NodeExecutionStatus.RUNNING)

    status = rig.advance(run_id)

    assert status is WorkflowRunStatus.WAITING_RUN
    assert [r.node_id for r in rig.store.node_executions(run_id)] == ["start", "a"]
    assert len(rig.launcher.launches) == 1
    assert rig.launcher.persisted_at_launch == [True]


def test_a_crash_between_persist_and_park_relaunches_with_the_same_id() -> None:
    """id 는 영속됐지만 파킹 전에 죽었다(Workflow 상태는 아직 `running`, 자식 행도 없음) -- 같은 id
    로
    다시 발사하고 파킹한다. 발사는 api 쪽에서 멱등이다."""
    rig = _Rig()
    run_id = rig.declare()
    child = uuid4()
    rig.store.seed(run_id, status=WorkflowRunStatus.RUNNING, status_seq=4, current_node_id="a")
    rig.store.seed_node(run_id, "start", NodeExecutionStatus.SUCCEEDED)
    rig.store.seed_node(run_id, "a", NodeExecutionStatus.WAITING_RUN, agent_run_id=child)

    status = rig.advance(run_id)

    assert status is WorkflowRunStatus.WAITING_RUN
    assert [launch.agent_run_id for launch in rig.launcher.launches] == [child]
    assert rig.execution(run_id).waiting_run_id == child
    assert len(rig.store.node_executions(run_id)) == 2


def test_two_agent_nodes_in_a_row_park_twice_with_distinct_children() -> None:
    """`START → A → B → END`: 첫 자식이 끝나면 B 를 발사해 다시 파킹한다(다른 id). 노드당 한 행."""
    rig = _Rig()
    run_id = rig.declare(agent_nodes=("a", "b"))
    rig.advance(run_id)
    first = rig.child_id(run_id, "a")
    rig.agent_runs.set_status(first, RunStatus.SUCCEEDED)

    status = rig.advance(run_id)

    assert status is WorkflowRunStatus.WAITING_RUN
    second = rig.child_id(run_id, "b")
    assert second != first
    assert rig.execution(run_id).waiting_run_id == second
    assert rig.execution(run_id).current_node_id == "b"
    assert [(r.node_id, r.status) for r in rig.store.node_executions(run_id)] == [
        ("start", NodeExecutionStatus.SUCCEEDED),
        ("a", NodeExecutionStatus.SUCCEEDED),
        ("b", NodeExecutionStatus.WAITING_RUN),
    ]
    rig.agent_runs.set_status(second, RunStatus.SUCCEEDED)
    assert rig.advance(run_id) is WorkflowRunStatus.SUCCEEDED
    assert len(rig.launcher.launches) == 2


def test_a_node_left_failed_by_a_crash_finishes_the_workflow_with_its_own_reason() -> None:
    """노드는 `failed` 로 마쳤는데 Workflow 를 끝내기 전에 죽었다 -- 노드에 남은 사유로 마저
    끝낸다."""
    rig = _Rig()
    run_id = rig.declare(requested_by=None)
    rig.advance(run_id)  # 첫 호출은 정상적으로 끝까지 간다
    execution = rig.execution(run_id)
    assert execution.status is WorkflowRunStatus.FAILED

    # 종결 직전 상태를 되돌려 재전달을 흉내낸다.
    rig.store.seed(run_id, status=WorkflowRunStatus.RUNNING, status_seq=4, current_node_id="a")

    status = rig.advance(run_id)

    assert status is WorkflowRunStatus.FAILED
    assert rig.execution(run_id).failure_reason == "workflow_run_without_requester"
    assert len(rig.store.node_executions(run_id)) == 2
