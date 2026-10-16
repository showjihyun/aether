"""spec 0005 2.2, D-11, R-1, R-3: 저장 시점 그래프 검증 — I/O 없는 순수 함수(AR-9).

여섯 거부(START 0개/2개 이상은 사유를 둘로 나눕니다)는 각각 다른 `Reason` 값입니다.
`DUPLICATE_NODE_ID` 는 spec 2.2 의 목록에 없던 여덟 번째입니다 — 2026-10-13 구현에서
발견했고 `DANGLING_EDGE` 와 같은 근거로 저장 때 잡습니다(spec 0005 개정 1).
`AGENT_NODE_WITHOUT_AGENT` 는 아홉 번째입니다(개정 3) — `agent_id` 없는 `AGENT` 노드.
`agent_id` 는 `AGENT` 가 아닌 노드에서 **무시**합니다(`max_iterations` 가 `LOOP` 아닌 노드에서
무시되는 것과 같은 규칙) — 거부하지 않습니다.
`CONDITION_NODE_WITHOUT_PREDICATE`·`CONDITION_NODE_WITHOUT_BOTH_BRANCHES` 는 열 번째와 열한
번째입니다(개정 4) - 판정식이 없는 `CONDITION`, 나가는 간선의 `label` 에 `true`·`false` 가 둘 다
있지 않은 `CONDITION`. 둘 다 실행 중에 발견하면 이미 자식 Run 을 띄운 뒤라 저장 때 잡습니다.
`LOOP` 은 `CONDITION` 과 같은 판정식을 쓰므로(개정 7 의 4) **같은 두 사유**를 적용받습니다 - 새
사유를
만들지 않습니다.
`WAIT_NODE_WITHOUT_DURATION` 은 열두 번째입니다(개정 7 (5)) - `wait_seconds` 가 없거나 0 이하인
`WAIT`. 얼마나 기다릴지 모르는 노드는 실행 중에 발견하면 이미 앞 노드들이 지나간 뒤입니다.
`wait_seconds` 는 `WAIT` 가 아닌 노드에서 **무시**합니다(`max_iterations` 와 같은 규칙).
`LLM_NODE_WITHOUT_PROMPT`·`TOOL_NODE_WITHOUT_TARGET` 은 열세 번째와 열네 번째입니다(개정 9 (4)) -
프롬프트 리터럴이 없는 `LLM`, 서버 또는 도구 이름이 없는 `TOOL`·`MCP`. 두 종류의 값은 다른 종류의
노드에서 **무시**합니다. **`AGENT_NODE_WITHOUT_AGENT` 의 뜻이 넓어졌습니다**: "Agent 참조가 필요한
노드에 참조가 없음" - `AGENT` 뿐 아니라 `TOOL`·`MCP` 도(권한 주체가 `agent_id` 입니다, 개정 9 (1))
이 사유를 씁니다. 값을 늘리지 않고 기존 사유를 재사용합니다.
한 정의가 여러 규칙을 어기면 위반을 전부 돌려줍니다. 한 위반이 다른 위반의 파생
증상으로 중복 보고되지 않도록, 고아 노드는 `END_UNREACHABLE` 에서 제외하고 끊긴
간선은 도달 가능성 계산에서 무시합니다.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from enum import StrEnum

from aether_workflow.domain.condition import ConditionOperator
from aether_workflow.domain.node import Node, NodeKind
from aether_workflow.domain.workflow_version import WorkflowVersion


class Reason(StrEnum):
    NO_START = "no_start"
    MULTIPLE_START = "multiple_start"
    END_UNREACHABLE = "end_unreachable"
    ORPHAN_NODE = "orphan_node"
    DANGLING_EDGE = "dangling_edge"
    DUPLICATE_NODE_ID = "duplicate_node_id"
    LOOP_WITHOUT_BOUND = "loop_without_bound"
    PARALLEL_WITHOUT_JOIN = "parallel_without_join"
    AGENT_NODE_WITHOUT_AGENT = "agent_node_without_agent"
    CONDITION_NODE_WITHOUT_PREDICATE = "condition_node_without_predicate"
    CONDITION_NODE_WITHOUT_BOTH_BRANCHES = "condition_node_without_both_branches"
    WAIT_NODE_WITHOUT_DURATION = "wait_node_without_duration"
    LLM_NODE_WITHOUT_PROMPT = "llm_node_without_prompt"
    TOOL_NODE_WITHOUT_TARGET = "tool_node_without_target"


@dataclass(frozen=True)
class Violation:
    reason: Reason
    node_id: str | None = None
    """위반이 가리키는 노드. START 개수처럼 그래프 전체에 대한 위반이면 `None`."""


_TOOL_KINDS = frozenset({NodeKind.TOOL, NodeKind.MCP})
_AGENT_REFERENCE_KINDS = frozenset({NodeKind.AGENT}) | _TOOL_KINDS


def _reachable(start: str, adjacency: dict[str, list[str]]) -> set[str]:
    seen = {start}
    queue = deque([start])
    while queue:
        for nxt in adjacency.get(queue.popleft(), []):
            if nxt not in seen:
                seen.add(nxt)
                queue.append(nxt)
    return seen


def _has_predicate(node: Node) -> bool:
    """`CONDITION` 의 판정식: 경로와 연산자, 그리고 (`exists` 가 아니면) 비교할 값."""
    if not node.condition_path or node.condition_operator is None:
        return False
    return node.condition_operator is ConditionOperator.EXISTS or node.condition_value is not None


def validate_version(version: WorkflowVersion) -> tuple[Violation, ...]:
    """위반이 없으면 빈 튜플. 결과 순서는 입력 순서와 무관하게 결정적입니다."""
    violations: list[Violation] = []
    ids = {n.id for n in version.nodes}
    kinds = {n.id: n.kind for n in version.nodes}

    seen_ids: set[str] = set()
    for node_id in sorted(n.id for n in version.nodes):
        if node_id in seen_ids:
            violations.append(Violation(Reason.DUPLICATE_NODE_ID, node_id))
        seen_ids.add(node_id)

    starts = sorted(n.id for n in version.nodes if n.kind is NodeKind.START)
    if not starts:
        violations.append(Violation(Reason.NO_START))
    elif len(starts) > 1:
        violations.append(Violation(Reason.MULTIPLE_START))

    valid_edges = []
    for e in sorted(version.edges, key=lambda e: (e.source, e.target, e.label or "")):
        for endpoint in (e.source, e.target):
            if endpoint not in ids:
                violations.append(Violation(Reason.DANGLING_EDGE, endpoint))
        if e.source in ids and e.target in ids:
            valid_edges.append(e)

    touched = {e.source for e in version.edges} | {e.target for e in version.edges}
    orphans = {n.id for n in version.nodes if n.id not in touched}
    for node_id in sorted(orphans):
        violations.append(Violation(Reason.ORPHAN_NODE, node_id))

    for n in sorted(version.nodes, key=lambda n: n.id):
        if n.kind is NodeKind.LOOP and (n.max_iterations is None or n.max_iterations <= 0):
            violations.append(Violation(Reason.LOOP_WITHOUT_BOUND, n.id))

    for n in sorted(version.nodes, key=lambda n: n.id):
        if n.kind in _AGENT_REFERENCE_KINDS and n.agent_id is None:
            violations.append(Violation(Reason.AGENT_NODE_WITHOUT_AGENT, n.id))

    for n in sorted(version.nodes, key=lambda n: n.id):
        if n.kind is NodeKind.LLM and not n.llm_prompt:
            violations.append(Violation(Reason.LLM_NODE_WITHOUT_PROMPT, n.id))
        if n.kind in _TOOL_KINDS and not (n.tool_server and n.tool_name):
            violations.append(Violation(Reason.TOOL_NODE_WITHOUT_TARGET, n.id))

    for n in sorted(version.nodes, key=lambda n: n.id):
        if n.kind is NodeKind.WAIT and (n.wait_seconds is None or n.wait_seconds <= 0):
            violations.append(Violation(Reason.WAIT_NODE_WITHOUT_DURATION, n.id))

    for n in sorted(version.nodes, key=lambda n: n.id):
        if n.kind not in (NodeKind.CONDITION, NodeKind.LOOP):
            continue
        if not _has_predicate(n):
            violations.append(Violation(Reason.CONDITION_NODE_WITHOUT_PREDICATE, n.id))
        labels = {e.label for e in version.edges if e.source == n.id}
        if not {"true", "false"} <= labels:
            violations.append(Violation(Reason.CONDITION_NODE_WITHOUT_BOTH_BRANCHES, n.id))

    forward: dict[str, list[str]] = {}
    backward: dict[str, list[str]] = {}
    for e in valid_edges:
        forward.setdefault(e.source, []).append(e.target)
        backward.setdefault(e.target, []).append(e.source)

    for n in sorted(version.nodes, key=lambda n: n.id):
        if n.kind is NodeKind.PARALLEL:
            downstream = _reachable(n.id, forward)
            if not any(kinds[i] is NodeKind.JOIN for i in downstream if i != n.id):
                violations.append(Violation(Reason.PARALLEL_WITHOUT_JOIN, n.id))

    ends = [n.id for n in version.nodes if n.kind is NodeKind.END]
    can_reach_end: set[str] = set()
    for end in ends:
        can_reach_end |= _reachable(end, backward)
    for n in sorted(version.nodes, key=lambda n: n.id):
        if n.id in orphans or n.id in can_reach_end:
            continue
        violations.append(Violation(Reason.END_UNREACHABLE, n.id))

    return tuple(violations)


class InvalidWorkflowGraph(Exception):
    """저장 시점 검증 실패. 유스케이스가 던지고 인바운드 어댑터가 4xx 로 옮깁니다(R-1)."""

    def __init__(self, violations: tuple[Violation, ...]) -> None:
        super().__init__(", ".join(v.reason.value for v in violations))
        self.violations = violations
