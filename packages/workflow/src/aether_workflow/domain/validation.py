"""spec 0005 2.2, D-11, R-1, R-3: 저장 시점 그래프 검증 — I/O 없는 순수 함수(AR-9).

여섯 거부(START 0개/2개 이상은 사유를 둘로 나눕니다)는 각각 다른 `Reason` 값입니다.
`DUPLICATE_NODE_ID` 는 spec 2.2 의 목록에 없던 여덟 번째입니다 — 2026-10-13 구현에서
발견했고 `DANGLING_EDGE` 와 같은 근거로 저장 때 잡습니다(spec 0005 개정 1).
`AGENT_NODE_WITHOUT_AGENT` 는 아홉 번째입니다(개정 3) — `agent_id` 없는 `AGENT` 노드.
`agent_id` 는 `AGENT` 가 아닌 노드에서 **무시**합니다(`max_iterations` 가 `LOOP` 아닌 노드에서
무시되는 것과 같은 규칙) — 거부하지 않습니다.
한 정의가 여러 규칙을 어기면 위반을 전부 돌려줍니다. 한 위반이 다른 위반의 파생
증상으로 중복 보고되지 않도록, 고아 노드는 `END_UNREACHABLE` 에서 제외하고 끊긴
간선은 도달 가능성 계산에서 무시합니다.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from enum import StrEnum

from aether_workflow.domain.node import NodeKind
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


@dataclass(frozen=True)
class Violation:
    reason: Reason
    node_id: str | None = None
    """위반이 가리키는 노드. START 개수처럼 그래프 전체에 대한 위반이면 `None`."""


def _reachable(start: str, adjacency: dict[str, list[str]]) -> set[str]:
    seen = {start}
    queue = deque([start])
    while queue:
        for nxt in adjacency.get(queue.popleft(), []):
            if nxt not in seen:
                seen.add(nxt)
                queue.append(nxt)
    return seen


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
        if n.kind is NodeKind.AGENT and n.agent_id is None:
            violations.append(Violation(Reason.AGENT_NODE_WITHOUT_AGENT, n.id))

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
