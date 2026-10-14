"""spec 0005 2.1, 2.3, 2.9 개정 2, 2.10, R-6, R-8, D-13 (P4-2a A): `AdvanceWorkflowRunUseCase` —
Workflow Run 을 `START` 에서 `END` 까지 전진시키는 실행기 골격. `AdvanceWorkflowRun`(inbound
포트)의 유일한 구현입니다.

**범위.** 지원하는 노드 종류는 `START`·`END` 둘입니다. 나머지 종류를 만나면 `failed` +
`unsupported_node_kind` 로 끝납니다(절반만 만든 노드를 두지 않습니다). 나가는 간선이 둘 이상이면
`failed` + `unsupported_branching` — 조용히 하나를 고르지 않습니다(분기는 P4-2b). 파킹·스위퍼·
자식 Run 은 PR B 이므로 이 유스케이스는 **대기 자체를 만들지 않습니다**: 호출은 lease 를 잡고,
끝까지 가거나 `failed` 로 끝내고, `finally` 에서 놓습니다.

**순서.** 선언 읽기(없으면 `RuntimeError`, lease 도 잡지 않음) → `acquire_lease`(실패면
`WorkflowLeaseHeld`) → `load`(종결이면 아무것도 하지 않고 그 상태를 돌려줌 — 멱등) →
`queued → running` → 현재 노드(없으면 `START`)부터 간선을 따라 전진 → `release`.

**멱등·재개의 축은 `start_node`.** `None` 은 "이미 기록돼 있다" 입니다(R-6, R-8). 이 경우 노드를
**다시 실행하지 않고** 기록이 `running` 으로 남아 있으면(시작만 하고 죽음) 새 행 없이 마무리하고,
이미 마쳤으면 건너뜁니다. 이 단계의 노드(`START`·`END`)는 실행할 것이 없어 "마무리" 가 곧 실행의
전부지만, 파킹이 생겨도 같은 축이 그대로 쓰입니다.

**`seq`.** Workflow Run 하나 안에서 1 부터 단조 증가하고 이벤트와 상태 통지가
**같은 수열**을 씁니다.
정본은 `data.workflow_run_executions.status_seq` 입니다. 비종결 이벤트는 **저장(`set_status`)한 뒤
발행**합니다 — 죽었다 깨어난 worker 가 같은 `seq` 를 다른 이벤트에 다시 쓰는 일이 없게(충돌 대신
빈틈을 택합니다. 빈틈은 `seq` 단조성을 해치지 않습니다). **종결 한 쌍(`workflow.status` +
`workflow.finished`)만 반대**입니다: 이벤트·통지를 먼저 내고 종결 상태를 **마지막에** 저장합니다.
그 사이에 죽으면 상태는 아직 `running` 이라 재전달된 요청이 같은 `seq` 로 한 쌍을 다시 내고(sink 가
같은 `seq` 를 흡수, api 투영은 `seq` 로 멱등) 끝냅니다 — 종결 상태를 먼저 저장하면 그 창에서
투영이 영영 `running` 으로 남는데 재전달은 "종결이면 아무것도 하지 않는다" 로 막히기 때문입니다.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from aether_workflow.application.ports.inbound.advance_workflow_run import WorkflowLeaseHeld
from aether_workflow.application.ports.outbound.clock import Clock
from aether_workflow.application.ports.outbound.workflow_event_sink import WorkflowEventSink
from aether_workflow.application.ports.outbound.workflow_run_declaration_reader import (
    WorkflowRunDeclaration,
    WorkflowRunDeclarationReader,
)
from aether_workflow.application.ports.outbound.workflow_run_state_store import (
    WorkflowRunStateStore,
)
from aether_workflow.application.ports.outbound.workflow_status_notifier import (
    WorkflowStatusMessage,
    WorkflowStatusNotifier,
)
from aether_workflow.domain.events import (
    NodeFinishedPayload,
    NodeStartedPayload,
    WorkflowEvent,
    WorkflowEventType,
    WorkflowFinishedPayload,
    WorkflowStatusPayload,
)
from aether_workflow.domain.failure import WorkflowFailureReason
from aether_workflow.domain.node import Node, NodeKind
from aether_workflow.domain.node_execution import NodeExecutionStatus
from aether_workflow.domain.run_status import (
    TERMINAL_STATUSES,
    IllegalWorkflowTransition,
    WorkflowRunStatus,
    can_transition,
)

_FIRST_ITERATION = 0
_SUPPORTED_KINDS = frozenset({NodeKind.START, NodeKind.END})


@dataclass
class _Cursor:
    """한 번의 전진 동안의 가변 위치 — `seq` 와 마지막으로 저장한 노드."""

    workflow_run_id: UUID
    seq: int
    node_id: str | None


class AdvanceWorkflowRunUseCase:
    """`AdvanceWorkflowRun` 의 구현."""

    def __init__(
        self,
        store: WorkflowRunStateStore,
        reader: WorkflowRunDeclarationReader,
        sink: WorkflowEventSink,
        notifier: WorkflowStatusNotifier,
        clock: Clock,
        *,
        owner: str,
        lease_ttl_seconds: float,
    ) -> None:
        self._store = store
        self._reader = reader
        self._sink = sink
        self._notifier = notifier
        self._clock = clock
        self._owner = owner
        self._lease_ttl_seconds = lease_ttl_seconds

    def __call__(self, workflow_run_id: UUID) -> WorkflowRunStatus:
        declaration = self._reader.declaration(workflow_run_id)
        if declaration is None:
            raise RuntimeError(f"no declaration for workflow run {workflow_run_id}")
        if not self._store.acquire_lease(workflow_run_id, self._owner, self._lease_ttl_seconds):
            raise WorkflowLeaseHeld(workflow_run_id)
        try:
            return self._advance(declaration)
        finally:
            self._store.release(workflow_run_id, self._owner)

    # -- 전진 ---------------------------------------------------------------

    def _advance(self, declaration: WorkflowRunDeclaration) -> WorkflowRunStatus:
        run_id = declaration.workflow_run_id
        execution = self._store.load(run_id)
        if execution is None:
            raise RuntimeError(f"lease acquired but no execution row for {run_id}")
        if execution.status in TERMINAL_STATUSES:
            return execution.status

        cursor = _Cursor(run_id, execution.status_seq, execution.current_node_id)
        if execution.status is not WorkflowRunStatus.RUNNING:
            self._to_running(cursor, execution.status, first_start=execution.started_at is None)

        nodes = {n.id: n for n in declaration.nodes}
        node = self._first_node(declaration, nodes, execution.current_node_id)
        if node is None:
            return self._finish(
                cursor, WorkflowRunStatus.FAILED, WorkflowFailureReason.INVALID_GRAPH
            )

        while True:
            if node.kind not in _SUPPORTED_KINDS:
                return self._finish(
                    cursor,
                    WorkflowRunStatus.FAILED,
                    WorkflowFailureReason.UNSUPPORTED_NODE_KIND,
                    node_id=node.id,
                )
            self._run_node(cursor, node)
            if node.kind is NodeKind.END:
                return self._finish(cursor, WorkflowRunStatus.SUCCEEDED, node_id=node.id)

            outgoing = [e for e in declaration.edges if e.source == node.id]
            if len(outgoing) > 1:
                return self._finish(
                    cursor,
                    WorkflowRunStatus.FAILED,
                    WorkflowFailureReason.UNSUPPORTED_BRANCHING,
                    node_id=node.id,
                )
            following = nodes.get(outgoing[0].target) if outgoing else None
            if following is None:
                return self._finish(
                    cursor,
                    WorkflowRunStatus.FAILED,
                    WorkflowFailureReason.INVALID_GRAPH,
                    node_id=node.id,
                )
            node = following

    @staticmethod
    def _first_node(
        declaration: WorkflowRunDeclaration, nodes: dict[str, Node], current_node_id: str | None
    ) -> Node | None:
        if current_node_id is not None:
            return nodes.get(current_node_id)
        return next((n for n in declaration.nodes if n.kind is NodeKind.START), None)

    def _to_running(
        self, cursor: _Cursor, current: WorkflowRunStatus, *, first_start: bool
    ) -> None:
        if not can_transition(current, WorkflowRunStatus.RUNNING):
            raise IllegalWorkflowTransition(current, WorkflowRunStatus.RUNNING)
        now = self._clock.now()
        started_at = now if first_start else None
        cursor.seq += 1
        self._store.set_status(
            cursor.workflow_run_id,
            WorkflowRunStatus.RUNNING,
            seq=cursor.seq,
            started_at=started_at,
        )
        self._publish(
            cursor,
            "workflow.status",
            WorkflowStatusPayload(status=WorkflowRunStatus.RUNNING.value).model_dump(
                exclude_none=True
            ),
            now,
        )
        self._notifier.notify(
            WorkflowStatusMessage(
                workflow_run_id=cursor.workflow_run_id,
                seq=cursor.seq,
                status=WorkflowRunStatus.RUNNING,
                at=now,
                started_at=started_at,
            )
        )

    # -- 노드 -----------------------------------------------------------------

    def _run_node(self, cursor: _Cursor, node: Node) -> None:
        """`START`·`END` 는 실행할 것이 없어 기록의 시작과 마침이 실행의 전부입니다."""
        run_id = cursor.workflow_run_id
        node_execution_id = self._store.start_node(run_id, node.id, _FIRST_ITERATION)
        if node_execution_id is not None:
            self._emit_node_event(
                cursor,
                "node.started",
                NodeStartedPayload(
                    node_id=node.id, kind=node.kind.value, iteration=_FIRST_ITERATION
                ).model_dump(),
                node.id,
            )
        else:
            # 이미 기록돼 있다 - 다시 실행하지 않습니다(R-6, R-8).
            record = next(
                (
                    r
                    for r in self._store.node_executions(run_id)
                    if r.node_id == node.id and r.iteration == _FIRST_ITERATION
                ),
                None,
            )
            if record is None or record.status is not NodeExecutionStatus.RUNNING:
                return
            node_execution_id = record.id
        self._store.finish_node(node_execution_id, NodeExecutionStatus.SUCCEEDED, self._clock.now())
        self._emit_node_event(
            cursor,
            "node.finished",
            NodeFinishedPayload(
                node_id=node.id,
                iteration=_FIRST_ITERATION,
                status=NodeExecutionStatus.SUCCEEDED.value,
            ).model_dump(),
            node.id,
        )

    def _emit_node_event(
        self, cursor: _Cursor, type_: WorkflowEventType, payload: dict[str, object], node_id: str
    ) -> None:
        """저장 먼저(`seq` 와 현재 노드), 발행은 그 다음."""
        cursor.seq += 1
        cursor.node_id = node_id
        self._store.set_status(
            cursor.workflow_run_id,
            WorkflowRunStatus.RUNNING,
            seq=cursor.seq,
            current_node_id=node_id,
        )
        self._publish(cursor, type_, payload, self._clock.now())

    # -- 종결 ---------------------------------------------------------------

    def _finish(
        self,
        cursor: _Cursor,
        status: WorkflowRunStatus,
        reason: WorkflowFailureReason | None = None,
        *,
        node_id: str | None = None,
    ) -> WorkflowRunStatus:
        """종결 한 쌍을 먼저 내고 종결 상태를 마지막에 저장합니다(모듈 docstring 참고)."""
        if not can_transition(WorkflowRunStatus.RUNNING, status):
            raise IllegalWorkflowTransition(WorkflowRunStatus.RUNNING, status)
        now = self._clock.now()
        final_node = node_id if node_id is not None else cursor.node_id
        status_seq = cursor.seq + 1
        finished_seq = cursor.seq + 2
        cursor.seq = status_seq
        self._publish(
            cursor,
            "workflow.status",
            WorkflowStatusPayload(
                status=status.value,
                current_node_id=final_node,
                failure_reason=reason.value if reason is not None else None,
            ).model_dump(exclude_none=True),
            now,
        )
        self._notifier.notify(
            WorkflowStatusMessage(
                workflow_run_id=cursor.workflow_run_id,
                seq=status_seq,
                status=status,
                at=now,
                current_node_id=final_node,
                finished_at=now,
                failure_reason=reason,
            )
        )
        cursor.seq = finished_seq
        self._publish(
            cursor,
            "workflow.finished",
            WorkflowFinishedPayload(status=status.value).model_dump(),
            now,
        )
        self._store.set_status(
            cursor.workflow_run_id,
            status,
            seq=finished_seq,
            current_node_id=final_node,
            failure_reason=reason,
            finished_at=now,
        )
        return status

    # -- 발행 ---------------------------------------------------------------

    def _publish(
        self,
        cursor: _Cursor,
        type_: WorkflowEventType,
        payload: dict[str, object],
        at: datetime,
    ) -> None:
        self._sink.publish(
            WorkflowEvent(
                workflow_run_id=cursor.workflow_run_id,
                seq=cursor.seq,
                at=at,
                type=type_,
                payload=payload,
            )
        )
