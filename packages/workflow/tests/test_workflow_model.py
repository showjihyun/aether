"""spec 0005 2.2, 2.3, D-11, D-12, D-14, R-1, R-2, R-3: Workflow 도메인과 검증의 계약 테스트.

컨테이너·네트워크·DB 없음 — 순수 함수만 검증합니다(AR-9).
"""

from __future__ import annotations

from uuid import UUID

import pytest
from aether_workflow.domain.condition import ConditionOperator
from aether_workflow.domain.node import Edge, Node, NodeKind
from aether_workflow.domain.run_status import (
    TERMINAL_STATUSES,
    WorkflowRunStatus,
    can_transition,
)
from aether_workflow.domain.serialization import serialize_version
from aether_workflow.domain.validation import Reason, Violation, validate_version
from aether_workflow.domain.workflow_version import WorkflowVersion

_AGENT_ID = UUID("00000000-0000-0000-0000-0000000000a1")


def _n(
    node_id: str,
    kind: NodeKind,
    max_iterations: int | None = None,
    agent_id: UUID | None = None,
) -> Node:
    """`AGENT` 는 기본으로 Agent 를, `CONDITION` 은 기본으로 판정식을 가집니다 — 다른 사유를 보려는
    테스트가 그 사유들로 오염되지 않게 합니다. 참조·판정식 없는 노드는 전용 테스트가
    직접 만듭니다."""
    if kind is NodeKind.AGENT and agent_id is None:
        agent_id = _AGENT_ID
    if kind is NodeKind.CONDITION:
        return Node(
            id=node_id,
            kind=kind,
            condition_path="input.q",
            condition_operator=ConditionOperator.EQUALS,
            condition_value="x",
        )
    return Node(id=node_id, kind=kind, max_iterations=max_iterations, agent_id=agent_id)


def _version(nodes: list[Node], edges: list[tuple[str, str]]) -> WorkflowVersion:
    return WorkflowVersion(
        number=1,
        nodes=tuple(nodes),
        edges=tuple(Edge(source=s, target=t) for s, t in edges),
    )


def _reasons(version: WorkflowVersion) -> set[Reason]:
    return {v.reason for v in validate_version(version)}


def _valid() -> WorkflowVersion:
    return WorkflowVersion(
        number=1,
        nodes=(
            _n("s", NodeKind.START),
            _n("a", NodeKind.AGENT),
            _n("c", NodeKind.CONDITION),
            _n("h", NodeKind.AGENT),
            _n("e", NodeKind.END),
        ),
        edges=(
            Edge("s", "a"),
            Edge("a", "c"),
            Edge("c", "h", "true"),
            Edge("c", "e", "false"),
            Edge("h", "e"),
        ),
    )


def test_node_kinds_are_exactly_thirteen() -> None:
    """spec D-14: 노드 종류는 열 열세 개이고 WEBHOOK·SCHEDULE 은 없다. `HUMAN`·`APPROVAL` 은 P4-4
    가 더했다(spec 2.6 개정 5 (5) - 둘은 v1 에서 같게 다룬다)."""
    assert {k.name for k in NodeKind} == {
        "START", "END", "AGENT", "CONDITION", "PARALLEL", "JOIN",
        "LOOP", "WAIT", "LLM", "MCP", "TOOL", "HUMAN", "APPROVAL",
    }  # fmt: skip


def test_valid_graph_passes() -> None:
    """spec 2.2: 올바른 그래프는 통과한다."""
    assert validate_version(_valid()) == ()


def test_no_start_rejected() -> None:
    """spec R-1: START 0개는 NO_START 로 거부된다."""
    v = _version([_n("a", NodeKind.AGENT), _n("e", NodeKind.END)], [("a", "e")])
    assert _reasons(v) == {Reason.NO_START}


def test_two_starts_rejected() -> None:
    """spec R-1: START 2개는 MULTIPLE_START 로 거부된다."""
    v = _version(
        [_n("s1", NodeKind.START), _n("s2", NodeKind.START), _n("e", NodeKind.END)],
        [("s1", "e"), ("s2", "e")],
    )
    assert _reasons(v) == {Reason.MULTIPLE_START}


def test_end_unreachable_rejected() -> None:
    """spec R-1: END 에 도달 못 하는 노드는 END_UNREACHABLE (고아와 구별)."""
    v = _version(
        [
            _n("s", NodeKind.START),
            _n("a", NodeKind.AGENT),
            _n("dead", NodeKind.AGENT),
            _n("e", NodeKind.END),
        ],
        [("s", "a"), ("a", "e"), ("a", "dead")],
    )
    assert _reasons(v) == {Reason.END_UNREACHABLE}


def test_orphan_rejected() -> None:
    """spec R-1: 간선이 하나도 없는 노드는 ORPHAN_NODE (도달 불가와 구별)."""
    v = _version(
        [
            _n("s", NodeKind.START),
            _n("e", NodeKind.END),
            _n("lonely", NodeKind.AGENT),
        ],
        [("s", "e")],
    )
    assert _reasons(v) == {Reason.ORPHAN_NODE}


def test_dangling_edge_rejected() -> None:
    """spec R-1: 없는 노드 id 를 가리키는 간선은 DANGLING_EDGE."""
    v = _version(
        [_n("s", NodeKind.START), _n("e", NodeKind.END)],
        [("s", "e"), ("s", "ghost")],
    )
    assert _reasons(v) == {Reason.DANGLING_EDGE}


def test_duplicate_node_id_rejected() -> None:
    """spec 0005 개정 1: 같은 id 를 가진 노드 둘은 DUPLICATE_NODE_ID.

    spec 2.2 의 여섯 거부에는 없었습니다. 2026-10-13 구현에서 발견한 구멍입니다 —
    중복 id 는 검증을 통과하고 저장에서 PK 충돌로 터지므로, "실행 중에 터지는 것을
    저장 때 잡는다"(DANGLING_EDGE 의 근거)와 같은 자리입니다. 4xx 로 사유를 주는
    쪽이 500 보다 낫습니다.
    """
    v = _version(
        [
            _n("s", NodeKind.START),
            _n("a", NodeKind.AGENT),
            _n("a", NodeKind.END),
            _n("e", NodeKind.END),
        ],
        [("s", "a"), ("a", "e")],
    )
    assert _reasons(v) == {Reason.DUPLICATE_NODE_ID}


@pytest.mark.parametrize("bad", [None, 0, -1])
def test_loop_without_positive_max_iterations_rejected(bad: int | None) -> None:
    """spec R-3, D-11: max_iterations 가 없거나 0 이하인 LOOP 는 거부된다."""
    v = _version(
        [_n("s", NodeKind.START), _n("l", NodeKind.LOOP, bad), _n("e", NodeKind.END)],
        [("s", "l"), ("l", "e")],
    )
    assert _reasons(v) == {Reason.LOOP_WITHOUT_BOUND}


def test_loop_with_positive_max_iterations_passes() -> None:
    """spec R-3: 양수 max_iterations 의 LOOP 는 통과한다."""
    v = _version(
        [_n("s", NodeKind.START), _n("l", NodeKind.LOOP, 3), _n("e", NodeKind.END)],
        [("s", "l"), ("l", "e")],
    )
    assert validate_version(v) == ()


def test_parallel_without_join_rejected() -> None:
    """spec R-1: 대응하는 JOIN 이 없는 PARALLEL 은 PARALLEL_WITHOUT_JOIN."""
    v = _version(
        [
            _n("s", NodeKind.START),
            _n("p", NodeKind.PARALLEL),
            _n("a", NodeKind.AGENT),
            _n("b", NodeKind.AGENT),
            _n("e", NodeKind.END),
        ],
        [("s", "p"), ("p", "a"), ("p", "b"), ("a", "e"), ("b", "e")],
    )
    assert _reasons(v) == {Reason.PARALLEL_WITHOUT_JOIN}


def test_parallel_with_join_passes() -> None:
    """spec 2.2: PARALLEL → 두 분기 → JOIN 은 통과한다."""
    v = _version(
        [
            _n("s", NodeKind.START),
            _n("p", NodeKind.PARALLEL),
            _n("a", NodeKind.AGENT),
            _n("b", NodeKind.AGENT),
            _n("j", NodeKind.JOIN),
            _n("e", NodeKind.END),
        ],
        [("s", "p"), ("p", "a"), ("p", "b"), ("a", "j"), ("b", "j"), ("j", "e")],
    )
    assert validate_version(v) == ()


def test_six_rejections_have_distinct_reasons() -> None:
    """spec R-1: 거부 사유는 값이 모두 다르고 개수가 고정이다.

    spec 2.2 의 여섯 거부 → 사유 여덟: START 0개/2개 이상을 둘로 나누고(R-1 이
    "각각" 을 요구합니다), spec 목록에 없던 `DUPLICATE_NODE_ID` 를 더했습니다
    (spec 0005 개정 1). 아홉 번째 `AGENT_NODE_WITHOUT_AGENT` 는 개정 3, 열 번째와 열한 번째
    (`CONDITION_NODE_WITHOUT_PREDICATE`·`CONDITION_NODE_WITHOUT_BOTH_BRANCHES`)는 개정 4 입니다.
    이 숫자를 늘릴 때는 spec 2.2 의 표도 함께 고칩니다 — 그래서 여기 상수로 못 박습니다.
    """
    assert len(list(Reason)) == 11
    assert len({r.value for r in Reason}) == 11


def test_agent_node_without_agent_rejected() -> None:
    """spec 0005 2.2 개정 3: `agent_id` 가 없는 AGENT 노드는 그 노드만 위반이다."""
    v = _version(
        [
            _n("s", NodeKind.START),
            _n("ok", NodeKind.AGENT),
            Node(id="bare", kind=NodeKind.AGENT),
            _n("e", NodeKind.END),
        ],
        [("s", "ok"), ("ok", "bare"), ("bare", "e")],
    )

    assert validate_version(v) == (Violation(Reason.AGENT_NODE_WITHOUT_AGENT, "bare"),)


def test_agent_version_alone_does_not_satisfy_the_reference() -> None:
    """spec 0005 2.2 개정 3: Agent 를 말하는 것은 `agent_id` 이고 `agent_version` 만으로는 부족."""
    v = _version(
        [
            _n("s", NodeKind.START),
            Node(id="a", kind=NodeKind.AGENT, agent_version=2),
            _n("e", NodeKind.END),
        ],
        [("s", "a"), ("a", "e")],
    )

    assert _reasons(v) == {Reason.AGENT_NODE_WITHOUT_AGENT}


def test_agent_with_id_and_optional_version_passes() -> None:
    """spec 0005 2.2 개정 3: `agent_version` 은 선택이다(없으면 실행 시점의 최신)."""
    v = _version(
        [
            _n("s", NodeKind.START),
            Node(id="a", kind=NodeKind.AGENT, agent_id=_AGENT_ID),
            Node(id="b", kind=NodeKind.AGENT, agent_id=_AGENT_ID, agent_version=3),
            _n("e", NodeKind.END),
        ],
        [("s", "a"), ("a", "b"), ("b", "e")],
    )

    assert validate_version(v) == ()


def test_agent_id_on_a_non_agent_node_is_ignored_not_rejected() -> None:
    """spec 0005 2.2 개정 3: `max_iterations` 가 LOOP 아닌 노드에서 무시되는 것과 같은 규칙 —
    없는 거부를 발명하지 않는다."""
    v = _version(
        [
            _n("s", NodeKind.START),
            Node(id="c", kind=NodeKind.LLM, agent_id=_AGENT_ID, max_iterations=5),
            _n("e", NodeKind.END),
        ],
        [("s", "c"), ("c", "e")],
    )

    assert validate_version(v) == ()


def test_serialization_is_byte_identical_and_order_independent() -> None:
    """spec R-2: 같은 정의는 바이트 동일, 노드·간선 입력 순서와 무관."""
    a = _valid()
    b = WorkflowVersion(
        number=a.number,
        nodes=tuple(reversed(a.nodes)),
        edges=tuple(reversed(a.edges)),
    )
    assert serialize_version(a) == serialize_version(a)
    assert isinstance(serialize_version(a), bytes)
    assert serialize_version(a) == serialize_version(b)


def test_serialization_differs_when_definition_differs() -> None:
    """spec R-2: 정의가 다르면 바이트도 다르다 (빈 직렬화 방지)."""
    other = _version([_n("s", NodeKind.START), _n("e", NodeKind.END)], [("s", "e")])
    assert serialize_version(_valid()) != serialize_version(other)


def test_serialization_differs_when_only_the_agent_reference_differs() -> None:
    """spec R-2: 두 정의가 `agent_id`(또는 `agent_version`)만 다르면 바이트가 달라야 한다 — 이
    단언이 없으면 새 필드가 직렬화에서 빠져도 R-2 가 공허하게 통과한다."""
    other_agent = UUID("00000000-0000-0000-0000-0000000000b2")

    def with_agent(agent_id: UUID, agent_version: int | None) -> WorkflowVersion:
        return _version(
            [
                _n("s", NodeKind.START),
                Node(id="a", kind=NodeKind.AGENT, agent_id=agent_id, agent_version=agent_version),
                _n("e", NodeKind.END),
            ],
            [("s", "a"), ("a", "e")],
        )

    base = serialize_version(with_agent(_AGENT_ID, None))
    assert base == serialize_version(with_agent(_AGENT_ID, None))
    assert base != serialize_version(with_agent(other_agent, None))
    assert base != serialize_version(with_agent(_AGENT_ID, 1))


def test_version_is_immutable() -> None:
    """spec D-12: WorkflowVersion 은 불변이다."""
    with pytest.raises(AttributeError):
        _valid().number = 2  # type: ignore[misc]


def test_status_values() -> None:
    """spec 2.3: 상태는 정확히 일곱 값이고 timed_out 이 없다."""
    assert {s.value for s in WorkflowRunStatus} == {
        "queued", "running", "waiting_run", "waiting_approval",
        "succeeded", "failed", "cancelled",
    }  # fmt: skip


@pytest.mark.parametrize(
    "terminal",
    [WorkflowRunStatus.SUCCEEDED, WorkflowRunStatus.FAILED, WorkflowRunStatus.CANCELLED],
)
def test_no_transition_out_of_terminal(terminal: WorkflowRunStatus) -> None:
    """spec 2.3: 종결 상태에서 나가는 전이는 없다."""
    for target in WorkflowRunStatus:
        assert not can_transition(terminal, target)


def test_terminal_set_is_exact() -> None:
    """spec 2.3: 종결은 succeeded·failed·cancelled 셋."""
    assert {s.value for s in TERMINAL_STATUSES} == {"succeeded", "failed", "cancelled"}


@pytest.mark.parametrize(
    "waiting", [WorkflowRunStatus.WAITING_RUN, WorkflowRunStatus.WAITING_APPROVAL]
)
def test_cancel_possible_while_waiting(waiting: WorkflowRunStatus) -> None:
    """spec 2.3: cancelled 는 대기 중에도 가능하다."""
    assert can_transition(waiting, WorkflowRunStatus.CANCELLED)


def test_normal_path_transitions() -> None:
    """spec 2.3: queued→running→waiting_run→running→succeeded 가능, queued→succeeded 불가."""
    S = WorkflowRunStatus
    assert can_transition(S.QUEUED, S.RUNNING)
    assert can_transition(S.RUNNING, S.WAITING_RUN)
    assert can_transition(S.WAITING_RUN, S.RUNNING)
    assert can_transition(S.RUNNING, S.SUCCEEDED)
    assert not can_transition(S.QUEUED, S.SUCCEEDED)


# --- P4-2b: CONDITION ------------------------------------------------------------------


def _cond(
    path: str | None = "input.q",
    operator: ConditionOperator | None = ConditionOperator.EQUALS,
    value: object = "x",
) -> Node:
    return Node(
        id="c",
        kind=NodeKind.CONDITION,
        condition_path=path,
        condition_operator=operator,
        condition_value=value,
    )


def _branching(node: Node, labels: list[str | None]) -> WorkflowVersion:
    targets = [f"t{i}" for i in range(len(labels))]
    return WorkflowVersion(
        number=1,
        nodes=(
            _n("s", NodeKind.START),
            node,
            *(_n(t, NodeKind.END) for t in targets),
        ),
        edges=(
            Edge("s", "c"),
            *(Edge("c", t, label) for t, label in zip(targets, labels, strict=True)),
        ),
    )


def test_condition_with_a_predicate_and_both_branches_passes() -> None:
    """spec 0005 2.2 개정 4: 판정식과 `true`·`false` 두 분기가 있으면 통과한다."""
    assert validate_version(_branching(_cond(), ["true", "false"])) == ()


def test_condition_exists_needs_no_value() -> None:
    """spec 개정 4: 연산자가 `exists` 면 `condition_value` 가 없다."""
    node = _cond(operator=ConditionOperator.EXISTS, value=None)
    assert validate_version(_branching(node, ["true", "false"])) == ()


@pytest.mark.parametrize(
    "node",
    [
        _cond(path=None),
        _cond(path=""),
        _cond(operator=None),
        _cond(value=None),  # `equals` 는 비교할 값이 있어야 한다
        Node(id="c", kind=NodeKind.CONDITION),
    ],
    ids=["no-path", "empty-path", "no-operator", "no-value", "bare"],
)
def test_condition_without_a_predicate_is_rejected(node: Node) -> None:
    """spec 0005 2.2 개정 4: 판정식이 없으면 실행 시점에 터지므로 저장 때 잡는다 - 그 노드만."""
    v = _branching(node, ["true", "false"])
    assert validate_version(v) == (Violation(Reason.CONDITION_NODE_WITHOUT_PREDICATE, "c"),)


@pytest.mark.parametrize(
    "labels",
    [["true"], ["false"], ["true", "true"], ["true", None], [None, None], ["yes", "no"]],
    ids=["only-true", "only-false", "true-twice", "true-and-unlabeled", "unlabeled", "other-names"],
)
def test_condition_without_both_branches_is_rejected(labels: list[str | None]) -> None:
    """spec 0005 2.2 개정 4: 나가는 간선의 label 에 `true`·`false` 가 **둘 다** 있어야 한다."""
    v = _branching(_cond(), labels)
    assert validate_version(v) == (Violation(Reason.CONDITION_NODE_WITHOUT_BOTH_BRANCHES, "c"),)


def test_the_two_condition_rejections_are_reported_together_and_distinctly() -> None:
    v = _branching(Node(id="c", kind=NodeKind.CONDITION), ["true"])
    assert _reasons(v) == {
        Reason.CONDITION_NODE_WITHOUT_PREDICATE,
        Reason.CONDITION_NODE_WITHOUT_BOTH_BRANCHES,
    }


def test_condition_settings_on_a_non_condition_node_are_ignored_not_rejected() -> None:
    """`agent_id` 와 같은 규칙 - 다른 종류의 노드에 있는 값은 무시한다."""
    v = _version(
        [
            _n("s", NodeKind.START),
            Node(id="a", kind=NodeKind.LLM, condition_path="input.q"),
            _n("e", NodeKind.END),
        ],
        [("s", "a"), ("a", "e")],
    )
    assert validate_version(v) == ()


def test_serialization_differs_when_only_a_condition_key_differs() -> None:
    """spec R-2: 세 키 각각이 직렬화에 들어 있다 - 빠지면 두 정의가 같은 바이트를 내고 R-2 가
    공허해진다."""

    def with_condition(node: Node) -> bytes:
        return serialize_version(_branching(node, ["true", "false"]))

    base = with_condition(_cond())
    assert base == with_condition(_cond())
    assert base != with_condition(_cond(path="input.other"))
    assert base != with_condition(_cond(operator=ConditionOperator.NOT_EQUALS))
    assert base != with_condition(_cond(value="y"))
