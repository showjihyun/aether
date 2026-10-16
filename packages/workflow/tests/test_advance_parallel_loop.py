"""spec 0005 2.7 개정 7, R-9, R-10, D-11, D-15 (P4-3 첫 물결): `PARALLEL`·`JOIN`·`LOOP` - fake
포트로,
컨테이너 없이(AR-9).

증명하는 것: 진행은 노드 실행 기록에서 읽는다(전진 가능한 노드 = 들어오는 간선의 출발 노드가 모두
마친 노드) / `PARALLEL` 의 분기가 모두 실행되고 `JOIN` 뒤 다음 노드가 한 번 / 분기 하나의 실패는
`JOIN` 에서 관측되어 Workflow 가 `branch_failed` 로 끝남(R-9) / `JOIN` 출력은 분기별이고 상한을
받음 /
`LOOP` 는 회차마다 본문 노드의 `iteration` 을 1 늘리고 상한을 넘기면 `loop_limit_exceeded`(R-10) /
조건으로 일찍 탈출 / 루프 안의 파킹은 같은 회차를 잇는다 / 타지 않은 `CONDITION` 분기의 하류는
전진하지
않는다.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

import pytest
from aether_runtime.domain.run import RunStatus
from aether_workflow.application.usecases.advance_workflow_run import AdvanceWorkflowRunUseCase
from aether_workflow.domain.condition import ConditionOperator
from aether_workflow.domain.failure import WorkflowFailureReason
from aether_workflow.domain.node import Edge, Node, NodeKind
from aether_workflow.domain.node_execution import NodeExecutionRecord, NodeExecutionStatus
from aether_workflow.domain.node_output import serialized_size
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

_AGENT = UUID("00000000-0000-0000-0000-0000000000a1")
_O = ConditionOperator


def _agent(node_id: str) -> Node:
    return Node(node_id, NodeKind.AGENT, agent_id=_AGENT)


class _Rig:
    def __init__(self, *, output_max_bytes: int = 8192) -> None:
        self.store = FakeWorkflowRunStateStore()
        self.reader = FakeWorkflowRunDeclarationReader()
        self.sink = FakeWorkflowEventSink()
        self.notifier = FakeWorkflowStatusNotifier()
        self.agent_runs = FakeAgentRunReader()
        self.launcher = FakeAgentRunLauncher(self.store)
        self.agent_runs.add_version(_AGENT, None)
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
            output_max_bytes=output_max_bytes,
        )

    def declare(
        self, nodes: tuple[Node, ...], edges: tuple[Edge, ...], input: dict[str, Any] | None = None
    ) -> UUID:
        return self.reader.add(nodes, edges, input=input, requested_by=REQUESTER)

    def records(self, run_id: UUID, node_id: str) -> list[NodeExecutionRecord]:
        return sorted(
            (r for r in self.store.node_executions(run_id) if r.node_id == node_id),
            key=lambda r: r.iteration,
        )

    def record(self, run_id: UUID, node_id: str) -> NodeExecutionRecord:
        (record,) = self.records(run_id, node_id)
        return record

    def visited(self, run_id: UUID) -> list[str]:
        return [r.node_id for r in self.store.node_executions(run_id)]

    def waiting(self, run_id: UUID) -> NodeExecutionRecord:
        (record,) = (
            r
            for r in self.store.node_executions(run_id)
            if r.status is NodeExecutionStatus.WAITING_RUN
        )
        return record

    def finish_waiting(
        self, run_id: UUID, text: str = "ok", status: RunStatus = RunStatus.SUCCEEDED
    ) -> NodeExecutionRecord:
        record = self.waiting(run_id)
        assert record.agent_run_id is not None
        self.agent_runs.set_status(record.agent_run_id, status)
        self.agent_runs.set_text(record.agent_run_id, text)
        return record

    def drive(
        self,
        run_id: UUID,
        outcomes: dict[str, tuple[str, RunStatus]] | None = None,
        *,
        after_child: Any = None,
    ) -> WorkflowRunStatus:
        """종결이 될 때까지: 파킹되면 기다리는 자식 Run 을 끝내고 다시 부른다."""
        outcomes = outcomes or {}
        for _ in range(60):
            status = self.advance(run_id)
            if status is not WorkflowRunStatus.WAITING_RUN:
                return status
            node_id = self.waiting(run_id).node_id
            text, child_status = outcomes.get(node_id, ("ok", RunStatus.SUCCEEDED))
            self.finish_waiting(run_id, text, child_status)
            if after_child is not None:
                after_child(run_id, node_id)
        raise AssertionError("never settled")

    def reason(self, run_id: UUID) -> str | None:
        execution = self.store.load(run_id)
        assert execution is not None
        return execution.failure_reason


def _diamond() -> tuple[tuple[Node, ...], tuple[Edge, ...]]:
    nodes = (
        Node("start", NodeKind.START),
        Node("p", NodeKind.PARALLEL),
        _agent("a"),
        _agent("b"),
        Node("j", NodeKind.JOIN),
        _agent("x"),
        Node("end", NodeKind.END),
    )
    edges = (
        Edge("start", "p"),
        Edge("p", "a"),
        Edge("p", "b"),
        Edge("a", "j"),
        Edge("b", "j"),
        Edge("j", "x"),
        Edge("x", "end"),
    )
    return nodes, edges


# --- PARALLEL / JOIN -----------------------------------------------------------------------


def test_every_branch_runs_and_the_node_after_the_join_runs_once() -> None:
    """R-9: 두 분기가 모두 실행되고 합류 뒤 다음 노드가 한 번 실행된다."""
    rig = _Rig()
    run_id = rig.declare(*_diamond())

    status = rig.drive(run_id)

    assert status is WorkflowRunStatus.SUCCEEDED
    assert sorted(rig.visited(run_id)) == sorted(["start", "p", "a", "b", "j", "x", "end"])
    assert len(rig.launcher.launches) == 3  # a, b, x - 합류 뒤 노드가 두 번 뜨지 않았다
    assert len(rig.records(run_id, "x")) == 1
    assert [r.status for r in rig.store.node_executions(run_id)].count(
        NodeExecutionStatus.SUCCEEDED
    ) == 7


@pytest.mark.parametrize("join_first", [False, True], ids=["join-last", "join-declared-first"])
def test_the_join_does_not_advance_until_every_incoming_node_has_finished(
    join_first: bool,
) -> None:
    """개정 7 (2): `JOIN` 은 들어오는 간선의 출발 노드가 모두 마쳐야 전진한다 - 선언 순서가 아니라
    기록이 정한다(`JOIN` 을 분기보다 먼저 선언해도 분기가 끝나기 전에 합류하지 않는다)."""
    rig = _Rig()
    nodes, edges = _diamond()
    if join_first:
        join = next(n for n in nodes if n.id == "j")
        rest = tuple(n for n in nodes if n.id != "j")
        nodes = (*rest[:2], join, *rest[2:])
    run_id = rig.declare(nodes, edges)

    assert rig.advance(run_id) is WorkflowRunStatus.WAITING_RUN
    assert rig.visited(run_id) == ["start", "p", "a"]
    rig.finish_waiting(run_id)

    assert rig.advance(run_id) is WorkflowRunStatus.WAITING_RUN  # b 가 떠서 파킹
    assert "j" not in rig.visited(run_id)
    assert "x" not in rig.visited(run_id)
    rig.finish_waiting(run_id)

    assert rig.advance(run_id) is WorkflowRunStatus.WAITING_RUN  # 합류 뒤 x
    assert rig.visited(run_id)[-2:] == ["j", "x"]


def test_the_join_output_is_per_branch() -> None:
    """개정 7 (3): `{"branches": {"<들어오는 노드 id>": <출력 또는 null>}}`."""
    rig = _Rig()
    run_id = rig.declare(*_diamond())

    rig.drive(run_id, {"a": ("alpha", RunStatus.SUCCEEDED), "b": ("beta", RunStatus.SUCCEEDED)})

    join = rig.record(run_id, "j")
    assert join.output == {
        "branches": {
            "a": {"text": "alpha", "status": "succeeded"},
            "b": {"text": "beta", "status": "succeeded"},
        }
    }
    assert join.output_truncated is False


def test_a_branch_without_output_is_null_in_the_join_output() -> None:
    """출력이 없는 분기 노드(`PARALLEL` 자신 등)는 `null` 이다."""
    rig = _Rig()
    nodes = (
        Node("start", NodeKind.START),
        Node("p", NodeKind.PARALLEL),
        Node("p2", NodeKind.PARALLEL),
        _agent("b"),
        Node("j", NodeKind.JOIN),
        Node("end", NodeKind.END),
    )
    edges = (
        Edge("start", "p"),
        Edge("p", "p2"),
        Edge("p", "b"),
        Edge("p2", "j"),
        Edge("b", "j"),
        Edge("j", "end"),
    )
    run_id = rig.declare(nodes, edges)

    assert rig.drive(run_id) is WorkflowRunStatus.SUCCEEDED
    assert rig.record(run_id, "j").output == {
        "branches": {"p2": None, "b": {"text": "ok", "status": "succeeded"}}
    }


def test_the_join_output_takes_the_same_byte_limit_and_marks_truncation() -> None:
    """개정 7 (3): P4-2b 의 상한과 잘림 표시를 그대로 받는다 - 분기 출력의 합이 상한을 넘으면 자르고
    `output_truncated` 를 함께 참으로 둔다."""
    rig = _Rig(output_max_bytes=120)
    run_id = rig.declare(*_diamond())

    rig.drive(
        run_id, {"a": ("A" * 400, RunStatus.SUCCEEDED), "b": ("B" * 400, RunStatus.SUCCEEDED)}
    )

    join = rig.record(run_id, "j")
    assert join.output_truncated is True
    assert join.output is not None
    assert serialized_size(join.output) <= 120
    assert set(join.output["branches"]) == {"a", "b"}
    assert rig.record(run_id, "a").output_truncated is True


def test_one_failed_branch_fails_the_run_at_the_join_after_the_other_branch_ran() -> None:
    """R-9: 분기 하나가 실패하면 합류 결과에 그 실패가 담기고 Workflow 가 `failed` +
    `branch_failed`. 다른 분기는 끝까지 실행된다."""
    rig = _Rig()
    run_id = rig.declare(*_diamond())

    status = rig.drive(run_id, {"a": ("boom", RunStatus.FAILED)})

    assert status is WorkflowRunStatus.FAILED
    assert rig.reason(run_id) == WorkflowFailureReason.BRANCH_FAILED.value
    assert rig.record(run_id, "a").status is NodeExecutionStatus.FAILED
    assert rig.record(run_id, "b").status is NodeExecutionStatus.SUCCEEDED
    join = rig.record(run_id, "j")
    assert join.status is NodeExecutionStatus.FAILED
    assert join.failure_reason == WorkflowFailureReason.BRANCH_FAILED.value
    assert join.output is not None
    assert join.output["branches"]["a"] == {"text": "boom", "status": "failed"}
    assert "x" not in rig.visited(run_id) and "end" not in rig.visited(run_id)
    assert rig.notifier.messages[-1].failure_reason is WorkflowFailureReason.BRANCH_FAILED


def test_a_failure_outside_any_branch_still_ends_the_run_with_its_own_reason() -> None:
    """분기 밖의 실패는 그 자리에서 Workflow 를 끝낸다 - `branch_failed` 로 덮지 않는다."""
    rig = _Rig()
    run_id = rig.declare(*_diamond())

    status = rig.drive(run_id, {"x": ("late", RunStatus.FAILED)})

    assert status is WorkflowRunStatus.FAILED
    assert rig.reason(run_id) == WorkflowFailureReason.AGENT_RUN_FAILED.value


def test_a_parallel_with_a_single_outgoing_edge_runs_as_one_branch() -> None:
    """저장 때 `parallel_without_join` 으로 이미 걸러지는 모양이지만 실행은 한 분기로 다룬다."""
    rig = _Rig()
    nodes = (
        Node("start", NodeKind.START),
        Node("p", NodeKind.PARALLEL),
        _agent("a"),
        Node("j", NodeKind.JOIN),
        Node("end", NodeKind.END),
    )
    edges = (Edge("start", "p"), Edge("p", "a"), Edge("a", "j"), Edge("j", "end"))
    run_id = rig.declare(nodes, edges)

    assert rig.drive(run_id) is WorkflowRunStatus.SUCCEEDED
    assert rig.record(run_id, "j").output == {
        "branches": {"a": {"text": "ok", "status": "succeeded"}}
    }


def test_seq_stays_strictly_increasing_across_branches() -> None:
    """`seq` 는 Workflow Run 안에서 단조 증가하고 이벤트·통지가 같은 수열을 쓴다 - 분기가
    둘이어도."""
    rig = _Rig()
    run_id = rig.declare(*_diamond())

    rig.drive(run_id)

    seqs = [e.seq for e in rig.sink.events]
    assert seqs == sorted(seqs)
    assert len(set(seqs)) == len(seqs)


def test_advancing_a_finished_parallel_run_again_changes_nothing() -> None:
    """R-8 의 멱등: 종결된 Run 을 다시 부르면 아무 것도 하지 않는다."""
    rig = _Rig()
    run_id = rig.declare(*_diamond())
    rig.drive(run_id)
    events, launches = len(rig.sink.events), len(rig.launcher.launches)

    assert rig.advance(run_id) is WorkflowRunStatus.SUCCEEDED

    assert (len(rig.sink.events), len(rig.launcher.launches)) == (events, launches)


# --- CONDITION 의 타지 않은 분기 ----------------------------------------------------------------


def test_the_downstream_of_an_untaken_condition_branch_does_not_advance() -> None:
    """개정 7 (2): `CONDITION` 이 고른 간선만 활성이다 - 타지 않은 분기의 하류는 전진하지 않는다."""
    rig = _Rig()
    nodes = (
        Node("start", NodeKind.START),
        Node(
            "cond",
            NodeKind.CONDITION,
            condition_path="input.q",
            condition_operator=_O.EQUALS,
            condition_value="go",
        ),
        _agent("yes"),
        _agent("no"),
        Node("end", NodeKind.END),
    )
    edges = (
        Edge("start", "cond"),
        Edge("cond", "yes", "true"),
        Edge("cond", "no", "false"),
        Edge("yes", "end"),
        Edge("no", "end"),
    )
    run_id = rig.declare(nodes, edges, input={"q": "go"})

    assert rig.drive(run_id) is WorkflowRunStatus.SUCCEEDED

    assert "no" not in rig.visited(run_id)
    assert len(rig.launcher.launches) == 1


# --- LOOP ------------------------------------------------------------------------------------


def _loop(
    *,
    max_iterations: int,
    path: str = "input.q",
    operator: ConditionOperator = _O.EQUALS,
    value: object = "go",
) -> tuple[tuple[Node, ...], tuple[Edge, ...]]:
    nodes = (
        Node("start", NodeKind.START),
        Node(
            "loop",
            NodeKind.LOOP,
            max_iterations=max_iterations,
            condition_path=path,
            condition_operator=operator,
            condition_value=value,
        ),
        _agent("work"),
        Node("end", NodeKind.END),
    )
    edges = (
        Edge("start", "loop"),
        Edge("loop", "work", "true"),
        Edge("work", "loop"),
        Edge("loop", "end", "false"),
    )
    return nodes, edges


def test_a_loop_over_its_bound_fails_on_the_n_plus_first_pass_with_its_own_reason() -> None:
    """R-10: 상한 n 인 루프가 n+1 회에 `failed` 가 되고 사유가 상한 초과로 구별된다."""
    rig = _Rig()
    run_id = rig.declare(*_loop(max_iterations=2), input={"q": "go"})

    status = rig.drive(run_id)

    assert status is WorkflowRunStatus.FAILED
    assert rig.reason(run_id) == WorkflowFailureReason.LOOP_LIMIT_EXCEEDED.value
    assert [r.iteration for r in rig.records(run_id, "loop")] == [0, 1, 2]
    assert rig.records(run_id, "loop")[2].status is NodeExecutionStatus.FAILED
    assert [r.iteration for r in rig.records(run_id, "work")] == [0, 1]
    assert len(rig.launcher.launches) == 2  # 본문은 상한만큼만 돌았다
    assert rig.notifier.messages[-1].failure_reason is WorkflowFailureReason.LOOP_LIMIT_EXCEEDED


def test_the_body_iteration_grows_by_one_per_pass() -> None:
    """개정 7 (4): 본문을 한 바퀴 돌 때마다 본문 노드의 `iteration` 이 1 늘고, 기록은 노드·회차당 한
    행이다(`unique(run, node, iteration)`)."""
    rig = _Rig()
    run_id = rig.declare(*_loop(max_iterations=3), input={"q": "go"})

    rig.drive(run_id)

    assert [r.iteration for r in rig.records(run_id, "work")] == [0, 1, 2]
    keys = [(r.node_id, r.iteration) for r in rig.store.node_executions(run_id)]
    assert len(keys) == len(set(keys))
    assert ("work", 1) in rig.store.start_node_calls
    started = [
        (e.payload["node_id"], e.payload["iteration"])
        for e in rig.sink.events
        if e.type == "node.started"
    ]
    assert ("work", 2) in started and ("loop", 3) in started


def test_a_loop_whose_condition_is_false_never_runs_the_body() -> None:
    rig = _Rig()
    run_id = rig.declare(*_loop(max_iterations=3), input={"q": "stop"})

    assert rig.drive(run_id) is WorkflowRunStatus.SUCCEEDED

    assert rig.visited(run_id) == ["start", "loop", "end"]
    assert [r.iteration for r in rig.records(run_id, "loop")] == [0]


def _run_with_body_texts(rig: _Rig, run_id: UUID, texts: list[str]) -> WorkflowRunStatus:
    """본문 `work` 가 회차마다 `texts` 의 다음 값을 출력하는 것으로 종결까지 몬다."""
    pending = iter(texts)
    for _ in range(40):
        status = rig.advance(run_id)
        if status is not WorkflowRunStatus.WAITING_RUN:
            return status
        rig.finish_waiting(run_id, next(pending))
    raise AssertionError("never settled")


@pytest.mark.parametrize(
    ("texts", "passes"),
    [(["done"], 1), (["more", "more", "done"], 3)],
    ids=["first-pass", "third-pass"],
)
def test_a_loop_exits_when_the_body_output_satisfies_the_condition(
    texts: list[str], passes: int
) -> None:
    """spec 0005 2.7 개정 8 (1), R-10: 판정식이 **본문 출력**(`nodes.work.text`)을 가리키면 첫
    판정에서는 본문 기록이 아직 없어 "계속"(참)으로 읽혀 본문이 돌고, 어떤 회차의 출력이 조건을
    만족시키면(`false` 간선) 상한 전에 탈출하고 `succeeded` 다."""
    rig = _Rig()
    run_id = rig.declare(
        *_loop(max_iterations=5, path="nodes.work.text", operator=_O.NOT_EQUALS, value="done"),
        input={},
    )

    status = _run_with_body_texts(rig, run_id, texts)

    assert status is WorkflowRunStatus.SUCCEEDED
    assert [r.iteration for r in rig.records(run_id, "work")] == list(range(passes))
    assert [r.iteration for r in rig.records(run_id, "loop")] == list(range(passes + 1))
    assert all(r.status is NodeExecutionStatus.SUCCEEDED for r in rig.records(run_id, "loop"))
    assert rig.visited(run_id)[-1] == "end"
    assert len(rig.launcher.launches) == passes


@pytest.mark.parametrize(
    ("path", "body_passes"),
    [("nodes.wrok.text", 0), ("nodes.work.txt", 1)],
    ids=["typo-node-id", "typo-field-after-body-ran"],
)
def test_a_loop_condition_pointing_at_a_typo_still_fails_loudly(
    path: str, body_passes: int
) -> None:
    """개정 8 (1): 완화는 **그래프에 있는 노드**의 기록이 아직 없을 때뿐이다. 그래프에 없는 노드 id
    (오타)는 첫 판정에서, 있는 노드의 없는 필드는 본문이 돈 뒤에 그대로 `condition_path_missing`
    이다
    - 조용한 거짓("계속")을 만들지 않는다."""
    rig = _Rig()
    run_id = rig.declare(
        *_loop(max_iterations=5, path=path, operator=_O.NOT_EQUALS, value="done"), input={}
    )

    status = _run_with_body_texts(rig, run_id, ["more"])

    assert status is WorkflowRunStatus.FAILED
    assert rig.reason(run_id) == WorkflowFailureReason.CONDITION_PATH_MISSING.value
    assert len(rig.records(run_id, "work")) == body_passes
    assert rig.records(run_id, "loop")[-1].status is NodeExecutionStatus.FAILED


def test_the_condition_node_does_not_get_the_unrecorded_node_relaxation() -> None:
    """개정 8 (1): `CONDITION` 에는 완화를 적용하지 않는다 - 그래프에 있는 노드(`later`)의 기록이
    아직 없어도 `condition_path_missing` 이다(그 노드는 상류가 실행된 자리에서만 평가된다)."""
    rig = _Rig()
    nodes = (
        Node("start", NodeKind.START),
        Node(
            "cond",
            NodeKind.CONDITION,
            condition_path="nodes.later.text",
            condition_operator=_O.EQUALS,
            condition_value="x",
        ),
        _agent("later"),
        Node("end", NodeKind.END),
    )
    edges = (
        Edge("start", "cond"),
        Edge("cond", "later", "true"),
        Edge("cond", "end", "false"),
        Edge("later", "end"),
    )
    run_id = rig.declare(nodes, edges, input={})

    assert rig.advance(run_id) is WorkflowRunStatus.FAILED
    assert rig.reason(run_id) == WorkflowFailureReason.CONDITION_PATH_MISSING.value


def test_a_park_inside_the_loop_resumes_the_same_pass_without_duplicating_it() -> None:
    """루프 안의 AGENT 파킹: 재개는 **같은 회차**를 잇고 회차가 중복·누락되지 않는다."""
    rig = _Rig()
    run_id = rig.declare(*_loop(max_iterations=2), input={"q": "go"})

    assert rig.advance(run_id) is WorkflowRunStatus.WAITING_RUN  # pass 0 파킹
    rig.finish_waiting(run_id)
    assert rig.advance(run_id) is WorkflowRunStatus.WAITING_RUN  # pass 1 파킹
    parked = rig.waiting(run_id)
    assert parked.iteration == 1
    events = len(rig.sink.events)

    # 자식이 아직 끝나지 않았는데 깨우는 신호가 또 왔다 - 아무 것도 바뀌지 않는다.
    assert rig.advance(run_id) is WorkflowRunStatus.WAITING_RUN
    assert len(rig.sink.events) == events
    assert [r.iteration for r in rig.records(run_id, "work")] == [0, 1]
    assert len(rig.launcher.launches) == 2

    # 이제 끝났다 - pass 1 을 마치고 loop 의 세 번째 판정에서 상한에 걸린다.
    rig.finish_waiting(run_id)
    assert rig.advance(run_id) is WorkflowRunStatus.FAILED
    assert rig.reason(run_id) == WorkflowFailureReason.LOOP_LIMIT_EXCEEDED.value
    assert [r.iteration for r in rig.records(run_id, "work")] == [0, 1]
    assert rig.records(run_id, "work")[1].agent_run_id == parked.agent_run_id
    assert len(rig.launcher.launches) == 2


def test_a_crash_after_the_loop_decision_resumes_without_a_second_pass_row() -> None:
    """R-6, R-8: loop 의 회차를 마치고 본문을 시작하기 전에 죽었다 - 재전달은 새 loop 행을 만들지
    않고 같은 회차의 본문으로 간다."""
    rig = _Rig()
    nodes, edges = _loop(max_iterations=3)
    run_id = rig.declare(nodes, edges, input={"q": "go"})
    rig.store.seed(run_id, status=WorkflowRunStatus.RUNNING, status_seq=4, current_node_id="loop")
    rig.store.seed_node(run_id, "start", NodeExecutionStatus.SUCCEEDED)
    rig.store.seed_node(run_id, "loop", NodeExecutionStatus.SUCCEEDED)

    assert rig.advance(run_id) is WorkflowRunStatus.WAITING_RUN

    assert [r.iteration for r in rig.records(run_id, "loop")] == [0]
    assert [r.iteration for r in rig.records(run_id, "work")] == [0]


def test_a_loop_condition_that_cannot_be_evaluated_fails_like_a_condition() -> None:
    rig = _Rig()
    run_id = rig.declare(*_loop(max_iterations=2, path="input.absent"), input={"q": "go"})

    assert rig.drive(run_id) is WorkflowRunStatus.FAILED
    assert rig.reason(run_id) == WorkflowFailureReason.CONDITION_PATH_MISSING.value
    assert rig.record(run_id, "loop").status is NodeExecutionStatus.FAILED
