"""spec 0005 2.2, 2.3, D-11, D-12, D-14, R-1, R-2, R-3: Workflow 도메인과 검증의 계약 테스트.

컨테이너·네트워크·DB 없음 — 순수 함수만 검증합니다(AR-9).
"""

from __future__ import annotations

import pytest
from aether_workflow.domain.node import Edge, Node, NodeKind
from aether_workflow.domain.run_status import (
    TERMINAL_STATUSES,
    WorkflowRunStatus,
    can_transition,
)
from aether_workflow.domain.serialization import serialize_version
from aether_workflow.domain.validation import Reason, validate_version
from aether_workflow.domain.workflow_version import WorkflowVersion


def _n(node_id: str, kind: NodeKind, max_iterations: int | None = None) -> Node:
    return Node(id=node_id, kind=kind, max_iterations=max_iterations)


def _version(nodes: list[Node], edges: list[tuple[str, str]]) -> WorkflowVersion:
    return WorkflowVersion(
        number=1,
        nodes=tuple(nodes),
        edges=tuple(Edge(source=s, target=t) for s, t in edges),
    )


def _reasons(version: WorkflowVersion) -> set[Reason]:
    return {v.reason for v in validate_version(version)}


def _valid() -> WorkflowVersion:
    return _version(
        [
            _n("s", NodeKind.START),
            _n("a", NodeKind.AGENT),
            _n("c", NodeKind.CONDITION),
            _n("h", NodeKind.AGENT),
            _n("e", NodeKind.END),
        ],
        [("s", "a"), ("a", "c"), ("c", "h"), ("h", "e")],
    )


def test_node_kinds_are_exactly_eleven() -> None:
    """spec D-14: 노드 종류는 열 한 개이고 WEBHOOK·SCHEDULE 은 없다."""
    assert {k.name for k in NodeKind} == {
        "START", "END", "AGENT", "CONDITION", "PARALLEL", "JOIN",
        "LOOP", "WAIT", "LLM", "MCP", "TOOL",
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
    (spec 0005 개정 1). 이 숫자를 늘릴 때는 spec 2.2 의 표도 함께 고칩니다 —
    그래서 여기 상수로 못 박습니다.
    """
    assert len(list(Reason)) == 8
    assert len({r.value for r in Reason}) == 8


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
