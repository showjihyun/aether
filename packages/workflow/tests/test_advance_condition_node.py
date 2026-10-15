"""spec 0005 2.4 개정 4, D-8, D-9, R-5 (P4-2b): 노드 출력과 `CONDITION` 분기 - fake 포트로,
컨테이너 없이(AR-9).

증명하는 것: `AGENT` 노드의 출력은 `{"text", "status"}` 이고 상한을 넘으면 자르고
플래그를 함께 남긴다 /
`START`·`END`·`CONDITION` 은 출력이 없다 / 분기는 간선의 `label` 이 정한다(선언 순서가 아니라) /
없는 경로·비교 불가 타입은 구별되는 사유로 실행 실패 / `CONDITION` 이 아닌 노드의 다중 간선은 여전히
`unsupported_branching` / 이벤트 payload 에 출력이 없다.
"""

from __future__ import annotations

import json
from typing import Any
from uuid import UUID

import pytest
from aether_runtime.domain.run import RunStatus
from aether_workflow.application.usecases.advance_workflow_run import AdvanceWorkflowRunUseCase
from aether_workflow.domain.condition import ConditionOperator
from aether_workflow.domain.failure import WorkflowFailureReason
from aether_workflow.domain.node import Edge, Node, NodeKind
from aether_workflow.domain.node_execution import NodeExecutionRecord, NodeExecutionStatus
from aether_workflow.domain.run_status import WorkflowRunStatus

from packages.workflow.tests.fakes import (
    REQUESTER,
    FakeAgentRunLauncher,
    FakeAgentRunReader,
    FakeWorkflowClock,
    FakeWorkflowEventSink,
    FakeWorkflowRunDeclarationReader,
    FakeWorkflowRunStateStore,
    FakeWorkflowStatusNotifier,
)

_AGENT = UUID("00000000-0000-0000-0000-0000000000a1")
_O = ConditionOperator


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
            launcher=self.launcher,
            owner="worker-a",
            lease_ttl_seconds=60.0,
            output_max_bytes=output_max_bytes,
        )

    def declare(
        self,
        *,
        path: str = "input.q",
        operator: ConditionOperator = _O.EQUALS,
        value: object = "go",
        input: dict[str, Any] | None = None,
        with_agent: bool = False,
        false_edge_first: bool = False,
        labels: tuple[str, ...] = ("true", "false"),
    ) -> UUID:
        cond = Node(
            "cond",
            NodeKind.CONDITION,
            condition_path=path,
            condition_operator=operator,
            condition_value=value,
        )
        head: tuple[Node, ...] = (Node("start", NodeKind.START),)
        chain: tuple[Edge, ...] = (Edge("start", "cond"),)
        if with_agent:
            head += (Node("ask", NodeKind.AGENT, agent_id=_AGENT),)
            chain = (Edge("start", "ask"), Edge("ask", "cond"))
        branches = [Edge("cond", f"end_{label}", label) for label in labels]
        if false_edge_first:
            branches.reverse()
        nodes = (*head, cond, *(Node(f"end_{label}", NodeKind.END) for label in labels))
        return self.reader.add(nodes, (*chain, *branches), input=input, requested_by=REQUESTER)

    def visited(self, run_id: UUID) -> list[str]:
        return [r.node_id for r in self.store.node_executions(run_id)]

    def record(self, run_id: UUID, node_id: str) -> NodeExecutionRecord:
        (record,) = (r for r in self.store.node_executions(run_id) if r.node_id == node_id)
        return record

    def finish_child(self, run_id: UUID, text: str | None, status: RunStatus) -> None:
        child = self.record(run_id, "ask").agent_run_id
        assert child is not None
        self.agent_runs.set_status(child, status)
        if text is not None:
            self.agent_runs.set_text(child, text)


# --- 분기 ----------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("q", "taken", "skipped"),
    [("go", "end_true", "end_false"), ("stop", "end_false", "end_true")],
)
def test_the_same_workflow_takes_a_different_path_for_a_different_input(
    q: str, taken: str, skipped: str
) -> None:
    """R-5 (단위 층): 같은 정의, 다른 입력 -> 지난 노드 목록이 다르다."""
    rig = _Rig()
    run_id = rig.declare(input={"q": q})

    status = rig.advance(run_id)

    assert status is WorkflowRunStatus.SUCCEEDED
    assert rig.visited(run_id) == ["start", "cond", taken]
    assert skipped not in rig.visited(run_id)


@pytest.mark.parametrize("false_edge_first", [False, True])
def test_the_branch_is_chosen_by_label_not_by_declaration_order(false_edge_first: bool) -> None:
    """간선을 선언한 순서가 아니라 `label` 이 가리키는 쪽으로 간다."""
    rig = _Rig()
    run_id = rig.declare(input={"q": "stop"}, false_edge_first=false_edge_first)

    rig.advance(run_id)

    assert rig.visited(run_id) == ["start", "cond", "end_false"]


def test_a_condition_can_branch_on_the_output_of_an_agent_node() -> None:
    """spec 개정 4 (1): 판정 대상은 선언된 맥락 - `nodes.<id>.<키>` 로 노드의 출력을 가리킨다."""
    rig = _Rig()
    run_id = rig.declare(path="nodes.ask.text", operator=_O.CONTAINS, value="yes", with_agent=True)
    assert rig.advance(run_id) is WorkflowRunStatus.WAITING_RUN

    rig.finish_child(run_id, "well, yes", RunStatus.SUCCEEDED)
    status = rig.advance(run_id)

    assert status is WorkflowRunStatus.SUCCEEDED
    assert rig.visited(run_id) == ["start", "ask", "cond", "end_true"]


def test_a_condition_can_branch_on_the_status_of_an_agent_node() -> None:
    rig = _Rig()
    run_id = rig.declare(
        path="nodes.ask.status", operator=_O.EQUALS, value="succeeded", with_agent=True
    )
    rig.advance(run_id)
    rig.finish_child(run_id, "x", RunStatus.SUCCEEDED)

    rig.advance(run_id)

    assert rig.visited(run_id)[-1] == "end_true"


def test_exists_on_a_missing_path_takes_the_false_branch() -> None:
    rig = _Rig()
    run_id = rig.declare(path="input.absent", operator=_O.EXISTS, value=None, input={"q": "go"})

    assert rig.advance(run_id) is WorkflowRunStatus.SUCCEEDED
    assert rig.visited(run_id) == ["start", "cond", "end_false"]


def test_a_missing_input_is_a_missing_path() -> None:
    rig = _Rig()
    run_id = rig.declare(input=None)

    assert rig.advance(run_id) is WorkflowRunStatus.FAILED
    execution = rig.store.load(run_id)
    assert execution is not None
    assert execution.failure_reason == WorkflowFailureReason.CONDITION_PATH_MISSING.value


# --- 실패 ----------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("kwargs", "reason"),
    [
        (
            {"path": "input.absent", "operator": _O.EQUALS, "value": "x"},
            WorkflowFailureReason.CONDITION_PATH_MISSING,
        ),
        (
            {"path": "nodes.ghost.text", "operator": _O.CONTAINS, "value": "x"},
            WorkflowFailureReason.CONDITION_PATH_MISSING,
        ),
        (
            {"path": "input.q", "operator": _O.GT, "value": 1},
            WorkflowFailureReason.CONDITION_TYPE_MISMATCH,
        ),
    ],
)
def test_an_unevaluable_condition_fails_the_run_with_its_own_reason(
    kwargs: dict[str, Any], reason: WorkflowFailureReason
) -> None:
    """spec 개정 4 (2): 조용한 거짓이 아니다 - 노드도 Workflow 도 그 사유로 실패하고 아무 분기로도
    가지 않는다."""
    rig = _Rig()
    run_id = rig.declare(input={"q": "go"}, **kwargs)

    status = rig.advance(run_id)

    assert status is WorkflowRunStatus.FAILED
    execution = rig.store.load(run_id)
    assert execution is not None
    assert execution.failure_reason == reason.value
    assert execution.current_node_id == "cond"
    assert rig.visited(run_id) == ["start", "cond"]
    record = rig.record(run_id, "cond")
    assert record.status is NodeExecutionStatus.FAILED
    assert record.failure_reason == reason.value
    assert rig.notifier.messages[-1].failure_reason is reason
    assert [e.payload["status"] for e in rig.sink.events if e.type == "node.finished"][-1] == (
        "failed"
    )


def test_a_branch_the_graph_does_not_have_fails_as_an_invalid_graph() -> None:
    """저장 시점 검증을 우회한 그래프도 멈추지 않고 `failed` 로 끝난다."""
    rig = _Rig()
    run_id = rig.declare(input={"q": "stop"}, labels=("true",))

    assert rig.advance(run_id) is WorkflowRunStatus.FAILED
    execution = rig.store.load(run_id)
    assert execution is not None
    assert execution.failure_reason == WorkflowFailureReason.INVALID_GRAPH.value


@pytest.mark.parametrize("kind", [NodeKind.START, NodeKind.AGENT])
def test_more_than_one_outgoing_edge_on_a_non_condition_node_is_still_refused(
    kind: NodeKind,
) -> None:
    """P4-2a 의 거부는 `CONDITION` 만 예외로 열렸다 - 다른 종류는 그대로 거부한다."""
    rig = _Rig()
    start = Node("start", NodeKind.START)
    nodes: tuple[Node, ...] = (start,)
    first = "start"
    edges: tuple[Edge, ...] = ()
    if kind is NodeKind.AGENT:
        nodes += (Node("ask", NodeKind.AGENT, agent_id=_AGENT),)
        edges += (Edge("start", "ask"),)
        first = "ask"
    nodes += (Node("x", NodeKind.END), Node("y", NodeKind.END))
    edges += (Edge(first, "x", "true"), Edge(first, "y", "false"))
    run_id = rig.reader.add(nodes, edges, requested_by=REQUESTER)
    if kind is NodeKind.AGENT:
        rig.advance(run_id)
        rig.finish_child(run_id, "t", RunStatus.SUCCEEDED)

    assert rig.advance(run_id) is WorkflowRunStatus.FAILED

    execution = rig.store.load(run_id)
    assert execution is not None
    assert execution.failure_reason == WorkflowFailureReason.UNSUPPORTED_BRANCHING.value
    assert "x" not in rig.visited(run_id) and "y" not in rig.visited(run_id)


# --- 출력 ----------------------------------------------------------------------------


def test_start_end_and_condition_have_no_output() -> None:
    """spec 개정 4: 출력이 없는 노드는 `NULL` 이다 - 빈 객체를 만들지 않는다."""
    rig = _Rig()
    run_id = rig.declare(input={"q": "go"})

    rig.advance(run_id)

    for node_id in ("start", "cond", "end_true"):
        record = rig.record(run_id, node_id)
        assert record.output is None, node_id
        assert record.output_truncated is False, node_id


def test_an_agent_node_records_text_and_terminal_status_as_its_output() -> None:
    rig = _Rig()
    run_id = rig.declare(path="nodes.ask.status", value="succeeded", with_agent=True)
    rig.advance(run_id)
    rig.finish_child(run_id, "the reply", RunStatus.SUCCEEDED)

    rig.advance(run_id)

    record = rig.record(run_id, "ask")
    assert record.output == {"text": "the reply", "status": "succeeded"}
    assert record.output_truncated is False


def test_a_long_reply_is_cut_to_the_limit_and_the_flag_is_recorded_with_it() -> None:
    """spec 개정 4 (4): 상한을 넘으면 자르고 `output_truncated` 를 **함께** 참으로 적는다."""
    rig = _Rig(output_max_bytes=120)
    run_id = rig.declare(path="nodes.ask.status", value="succeeded", with_agent=True)
    rig.advance(run_id)
    rig.finish_child(run_id, "안녕하세요 " * 200, RunStatus.SUCCEEDED)

    rig.advance(run_id)

    record = rig.record(run_id, "ask")
    assert record.output_truncated is True
    assert record.output is not None
    assert record.output["status"] == "succeeded"
    text = record.output["text"]
    assert isinstance(text, str) and text and ("안녕하세요 " * 200).startswith(text)
    assert len(json.dumps(record.output, ensure_ascii=False, separators=(",", ":")).encode()) <= 120


def test_a_child_without_an_assistant_message_has_an_empty_text() -> None:
    rig = _Rig()
    run_id = rig.declare(path="nodes.ask.status", value="failed", with_agent=True)
    rig.advance(run_id)
    rig.finish_child(run_id, None, RunStatus.FAILED)

    assert rig.advance(run_id) is WorkflowRunStatus.FAILED

    record = rig.record(run_id, "ask")
    assert record.output == {"text": "", "status": "failed"}
    assert record.status is NodeExecutionStatus.FAILED


def test_event_payloads_do_not_carry_the_output() -> None:
    """spec 2.4: 출력은 `data` 의 노드 실행 기록에만 둔다 - 이벤트·통지에는 없다(C-3)."""
    rig = _Rig()
    secret = "SECRET-REPLY-BODY"
    run_id = rig.declare(path="nodes.ask.status", value="succeeded", with_agent=True)
    rig.advance(run_id)
    rig.finish_child(run_id, secret, RunStatus.SUCCEEDED)

    rig.advance(run_id)

    for event in rig.sink.events:
        assert secret not in repr(event.payload)
    for message in rig.notifier.messages:
        assert secret not in repr(message)
    finished = [e.payload for e in rig.sink.events if e.type == "node.finished"]
    assert all(set(p) == {"node_id", "iteration", "status"} for p in finished)


# --- 재개 ----------------------------------------------------------------------------


def test_a_condition_left_running_by_a_crash_is_finished_once_and_routed() -> None:
    """R-6/R-8: 시작만 하고 죽은 `CONDITION` 은 새 행 없이 마무리하고 같은 분기로 간다."""
    rig = _Rig()
    run_id = rig.declare(input={"q": "stop"})
    rig.store.seed(run_id, status=WorkflowRunStatus.RUNNING, status_seq=3, current_node_id="cond")
    rig.store.seed_node(run_id, "start", NodeExecutionStatus.SUCCEEDED)
    rig.store.seed_node(run_id, "cond", NodeExecutionStatus.RUNNING)

    assert rig.advance(run_id) is WorkflowRunStatus.SUCCEEDED

    assert rig.visited(run_id) == ["start", "cond", "end_false"]
    assert rig.record(run_id, "cond").status is NodeExecutionStatus.SUCCEEDED


def test_a_condition_finished_before_the_crash_routes_again_the_same_way() -> None:
    """노드는 마쳤는데 다음 노드로 가기 전에 죽었다 - 판정은 순수 함수라 같은 분기로 간다."""
    rig = _Rig()
    run_id = rig.declare(input={"q": "go"})
    rig.store.seed(run_id, status=WorkflowRunStatus.RUNNING, status_seq=3, current_node_id="cond")
    rig.store.seed_node(run_id, "start", NodeExecutionStatus.SUCCEEDED)
    rig.store.seed_node(run_id, "cond", NodeExecutionStatus.SUCCEEDED)

    assert rig.advance(run_id) is WorkflowRunStatus.SUCCEEDED

    assert rig.visited(run_id) == ["start", "cond", "end_true"]
