"""spec 0005 2.7 개정 7 (2, 4): 진행을 **노드 실행 기록에서 읽는** 순수 함수들 - I/O 없음(AR-9).

분기가 둘 이상이면 "현재 노드" 하나로 진행을 말할 수 없습니다. 그래서 선언(노드·간선)과 노드 실행
기록(`NodeExecutionRecord`)만으로 **다음에 전진할 수 있는 노드**를 유도합니다.

**노드 인스턴스.** 노드 하나의 한 회차 - `(노드 id, iteration)`. `LOOP` 본문이 아니면 회차는 0
하나입니다.

**전진 가능한 노드(READY).** 들어오는 간선이 모두 **결판난**(활성 또는 비활성) 노드 중, 활성 간선이
하나 이상이고 아직 자기 기록이 없는 노드. 간선의 상태:

| 출발 노드(인스턴스) | 간선 |
| --- | --- |
| `succeeded` 이고 `CONDITION`·`LOOP` 이 아님 (`PARALLEL` 포함 - 나가는 간선 전부) | 활성 |
| `succeeded` 인 `CONDITION`·`LOOP` | 고른 `label` 의 간선만 활성, 나머지는 비활성 |
| 타지 않은 분기의 하류(기록 없이 SKIPPED) | 비활성 |
| `failed` 이거나 실패에 막힌(BLOCKED) 노드 | 막힘 - 하류로 전파되고 **`JOIN` 만** 이를 관측합니다 |
| 아직 마치지 않음 | 결판 안 남 |

`JOIN` 은 특수 분기 없이 같은 규칙을 받습니다: 들어오는 간선이 모두 결판나야 전진하고, 막힌 간선이
하나라도 있으면 전진해서(READY) 실패를 기록합니다.

**고른 분기(`chosen`).** `CONDITION`·`LOOP` 의 판정은 영속하지 않습니다(spec 개정 4). 이미 마친
노드의 분기는 **기록에서 먼저** 읽습니다 - 한쪽 하류만 시작했으면 그쪽이고, 어느 쪽도 시작하지
않았으면 같은 맥락으로 다시 판정합니다(`decide`). 본문이 돈 뒤에는 맥락이 바뀌어 다시 판정하면
틀릴 수 있으므로 기록이 먼저입니다.

**`LOOP` 의 회차.** `LOOP` 노드 자신의 회차는 지금까지 판정한 횟수입니다 - 마지막 기록이
`succeeded` 이고
`true` 로 갔으면 다음 회차(= 마지막 + 1), 아니면 마지막 회차. 본문 노드의 회차는 그 `LOOP` 의 마지막
회차(`pass`)입니다. 본문 = `true` 간선의 대상에서 시작해 그 `LOOP` 로 돌아오기 전까지 닿는 노드들.
회차 0 의 `LOOP` 는 루프 밖에서 들어오는 간선을, 회차 k>0 의 `LOOP` 는 본문 끝에서 돌아오는 간선(
회차 k-1)을 입력으로 봅니다. 본문이 `LOOP` 보다 먼저 한 번 도는 do-while 모양과 `LOOP` 의 중첩은 v1
범위 밖입니다(`PARALLEL`·`JOIN` 의 중첩 짝 맞추기를 검사하지 않는 것과 같은 선, 개정 1).
"""

from __future__ import annotations

from collections import deque
from collections.abc import Callable, Iterable, Sequence
from enum import StrEnum

from aether_workflow.domain.node import Edge, Node, NodeKind
from aether_workflow.domain.node_execution import NodeExecutionRecord, NodeExecutionStatus

_LABELS = {True: "true", False: "false"}
_BRANCHING = frozenset({NodeKind.CONDITION, NodeKind.LOOP})


class InstanceState(StrEnum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    IN_PROGRESS = "in_progress"
    """기록이 있고 아직 마치지 않았다(`running`·`waiting_run`·`waiting_approval`)."""
    READY = "ready"
    """기록은 없고 전진할 수 있다."""
    WAITING = "waiting"
    """기록은 없고 들어오는 간선이 아직 결판나지 않았다."""
    SKIPPED = "skipped"
    """기록은 없고 앞으로도 실행되지 않는다(타지 않은 분기)."""
    BLOCKED = "blocked"
    """기록은 없고 앞으로도 실행되지 않는다(실패한 노드의 하류)."""


class _EdgeState(StrEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    BLOCKED = "blocked"
    UNRESOLVED = "unresolved"


def branch_members(nodes: Sequence[Node], edges: Sequence[Edge]) -> frozenset[str]:
    """`PARALLEL` 에서 `JOIN` 까지의 분기 안에 있는 노드들(`JOIN` 은 제외). 이 노드가 실패하면
    Workflow 를 그 자리에서 끝내지 않고 다른 분기를 마저 돌린 뒤 `JOIN` 에서 관측합니다(R-9)."""
    kinds = {n.id: n.kind for n in nodes}
    outgoing: dict[str, list[str]] = {}
    for e in edges:
        outgoing.setdefault(e.source, []).append(e.target)
    members: set[str] = set()
    for node in nodes:
        if node.kind is not NodeKind.PARALLEL:
            continue
        queue = deque(outgoing.get(node.id, ()))
        while queue:
            current = queue.popleft()
            if current in members or current == node.id or kinds.get(current) is NodeKind.JOIN:
                continue
            members.add(current)
            queue.extend(outgoing.get(current, ()))
    return frozenset(members)


class Progress:
    """한 시점의 선언과 기록에서 유도한 진행. 만든 뒤 바꾸지 않습니다."""

    def __init__(
        self,
        nodes: Sequence[Node],
        edges: Sequence[Edge],
        records: Iterable[NodeExecutionRecord],
        decide: Callable[[Node], bool | None],
    ) -> None:
        """`decide(node)` 는 `CONDITION`·`LOOP` 의 판정식을 지금 맥락으로 평가합니다. 판정할 수
        없으면 `None`."""
        self._nodes = tuple(nodes)
        self._by_id = {n.id: n for n in self._nodes}
        self._incoming: dict[str, list[Edge]] = {n.id: [] for n in self._nodes}
        self._outgoing: dict[str, list[Edge]] = {n.id: [] for n in self._nodes}
        for e in edges:
            if e.source in self._by_id and e.target in self._by_id:
                self._incoming[e.target].append(e)
                self._outgoing[e.source].append(e)
        self._records: dict[str, dict[int, NodeExecutionRecord]] = {}
        for r in records:
            self._records.setdefault(r.node_id, {})[r.iteration] = r
        self._decide = decide
        self._bodies = {n.id: self._body(n) for n in self._nodes if n.kind is NodeKind.LOOP}
        self._loop_of: dict[str, str] = {}
        for loop_id, body in sorted(self._bodies.items(), key=lambda item: -len(item[1])):
            for member in body:
                self._loop_of[member] = loop_id  # 가장 작은 본문이 마지막에 덮어쓴다
        self._states: dict[tuple[str, int], InstanceState] = {}
        self._chosen: dict[tuple[str, int], str | None] = {}
        self._visiting: set[tuple[str, int]] = set()

    def _body(self, loop: Node) -> frozenset[str]:
        body: set[str] = set()
        stack = [e.target for e in self._outgoing[loop.id] if e.label == "true"]
        while stack:
            current = stack.pop()
            if current == loop.id or current in body:
                continue
            body.add(current)
            stack.extend(e.target for e in self._outgoing[current])
        return frozenset(body)

    # -- 회차 ---------------------------------------------------------------

    def _last_iteration(self, node_id: str) -> int | None:
        recorded = self._records.get(node_id)
        return max(recorded) if recorded else None

    def iteration(self, node_id: str) -> int:
        """노드의 **지금** 회차."""
        node = self._by_id[node_id]
        if node.kind is NodeKind.LOOP:
            last = self._last_iteration(node_id)
            if last is None:
                return 0
            record = self._records[node_id][last]
            if (
                record.status is NodeExecutionStatus.SUCCEEDED
                and self._chosen_label(node, last) == "true"
            ):
                return last + 1
            return last
        loop_id = self._loop_of.get(node_id)
        if loop_id is None:
            return 0
        return self._last_iteration(loop_id) or 0

    # -- 분기 ---------------------------------------------------------------

    def _started(self, node: Node, iteration: int, edge: Edge) -> bool:
        target = edge.target
        recorded = self._records.get(target, {})
        if node.kind is NodeKind.LOOP and target in self._bodies[node.id]:
            return iteration in recorded
        loop_id = self._loop_of.get(node.id)
        if loop_id is not None and self._loop_of.get(target) == loop_id:
            return iteration in recorded
        return bool(recorded)

    def _chosen_label(self, node: Node, iteration: int) -> str | None:
        key = (node.id, iteration)
        if key in self._chosen:
            return self._chosen[key]
        out = self._outgoing[node.id]
        true_started = any(self._started(node, iteration, e) for e in out if e.label == "true")
        false_started = any(self._started(node, iteration, e) for e in out if e.label == "false")
        label: str | None
        if true_started != false_started:
            label = "true" if true_started else "false"
        else:
            decided = self._decide(node)
            label = None if decided is None else _LABELS[decided]
        self._chosen[key] = label
        return label

    # -- 상태 ---------------------------------------------------------------

    def _source_iteration(self, edge: Edge, target_iteration: int) -> int:
        source, target = self._by_id[edge.source], self._by_id[edge.target]
        if source.kind is NodeKind.LOOP:
            if target.id in self._bodies[source.id]:
                return target_iteration
            return self._last_iteration(source.id) or 0
        if target.kind is NodeKind.LOOP and source.id in self._bodies[target.id]:
            return target_iteration - 1
        loop_id = self._loop_of.get(source.id)
        if loop_id is not None:
            if self._loop_of.get(target.id) == loop_id:
                return target_iteration
            return self._last_iteration(loop_id) or 0
        return 0

    def _edge_state(self, edge: Edge, target_iteration: int) -> _EdgeState:
        source = self._by_id[edge.source]
        source_iteration = self._source_iteration(edge, target_iteration)
        state = self._state_at(source.id, source_iteration)
        if state is InstanceState.SUCCEEDED:
            if source.kind not in _BRANCHING:
                return _EdgeState.ACTIVE
            label = self._chosen_label(source, source_iteration)
            if label == edge.label:
                return _EdgeState.ACTIVE
            if source.kind is NodeKind.LOOP and label == "true" and edge.label == "false":
                return _EdgeState.UNRESOLVED  # 아직 도는 중이다 - 탈출은 마지막 판정이 정한다
            return _EdgeState.INACTIVE
        if state in (InstanceState.FAILED, InstanceState.BLOCKED):
            return _EdgeState.BLOCKED
        if state is InstanceState.SKIPPED:
            return _EdgeState.INACTIVE
        return _EdgeState.UNRESOLVED

    def _inputs(self, node: Node, iteration: int) -> list[Edge]:
        edges = self._incoming[node.id]
        if node.kind is not NodeKind.LOOP:
            return edges
        body = self._bodies[node.id]
        if iteration == 0:
            return [e for e in edges if e.source not in body]
        return [e for e in edges if e.source in body]

    def _state_at(self, node_id: str, iteration: int) -> InstanceState:
        key = (node_id, iteration)
        cached = self._states.get(key)
        if cached is not None:
            return cached
        record = self._records.get(node_id, {}).get(iteration)
        if record is not None:
            if record.status is NodeExecutionStatus.SUCCEEDED:
                state = InstanceState.SUCCEEDED
            elif record.status is NodeExecutionStatus.FAILED:
                state = InstanceState.FAILED
            else:
                state = InstanceState.IN_PROGRESS
            self._states[key] = state
            return state
        if key in self._visiting:
            return InstanceState.WAITING
        self._visiting.add(key)
        try:
            state = self._derive(self._by_id[node_id], iteration)
        finally:
            self._visiting.discard(key)
        self._states[key] = state
        return state

    def _derive(self, node: Node, iteration: int) -> InstanceState:
        inputs = self._inputs(node, iteration)
        if not inputs:
            return InstanceState.READY if node.kind is NodeKind.START else InstanceState.SKIPPED
        states = [self._edge_state(e, iteration) for e in inputs]
        if _EdgeState.UNRESOLVED in states:
            return InstanceState.WAITING
        blocked = _EdgeState.BLOCKED in states
        active = _EdgeState.ACTIVE in states
        if node.kind is NodeKind.JOIN:
            return InstanceState.READY if blocked or active else InstanceState.SKIPPED
        if blocked:
            return InstanceState.BLOCKED
        return InstanceState.READY if active else InstanceState.SKIPPED

    # -- 질의 ---------------------------------------------------------------

    def state(self, node_id: str) -> InstanceState:
        return self._state_at(node_id, self.iteration(node_id))

    def next_ready(self) -> tuple[Node, int] | None:
        """다음에 전진할 노드와 그 회차. 이미 시작한 노드(재개)가 먼저, 그 안에서는 선언 순서."""
        resuming: tuple[Node, int] | None = None
        fresh: tuple[Node, int] | None = None
        for node in self._nodes:
            iteration = self.iteration(node.id)
            state = self._state_at(node.id, iteration)
            if state is InstanceState.IN_PROGRESS and resuming is None:
                resuming = (node, iteration)
            elif state is InstanceState.READY and fresh is None:
                fresh = (node, iteration)
        return resuming or fresh

    def incoming_sources(self, node_id: str) -> tuple[str, ...]:
        """들어오는 간선의 출발 노드 id (중복 없이, 선언 순서)."""
        seen: dict[str, None] = {}
        for e in self._incoming[node_id]:
            seen.setdefault(e.source, None)
        return tuple(seen)

    def has_blocked_input(self, node_id: str) -> bool:
        """들어오는 간선 중 실패에 막힌 것이 있는가 - `JOIN` 이 분기 실패를 관측하는 자리."""
        node = self._by_id[node_id]
        iteration = self.iteration(node_id)
        return any(
            self._edge_state(e, iteration) is _EdgeState.BLOCKED
            for e in self._inputs(node, iteration)
        )

    def outgoing_count(self, node_id: str) -> int:
        return len(self._outgoing[node_id])
