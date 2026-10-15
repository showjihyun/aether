"""spec 0005 2.1, 2.3, 2.9 개정 2, 2.10, R-6, R-8, D-13 (P4-2a A): `AdvanceWorkflowRunUseCase` —
Workflow Run 을 `START` 에서 `END` 까지 전진시키는 실행기 골격. `AdvanceWorkflowRun`(inbound
포트)의 유일한 구현입니다.

**범위.** 지원하는 노드 종류는 `START`·`END`·`AGENT`·`CONDITION`·`HUMAN`·`APPROVAL` 여섯입니다
(`HUMAN`·`APPROVAL` 은 v1 에서 같게 `waiting_approval` 로 파킹합니다, P4-4). 나머지 종류를 만나면
`failed` + `unsupported_node_kind` 로 끝납니다(절반만 만든 노드를 두지 않습니다). 나가는 간선이
둘 이상인 노드는 `CONDITION` 만 예외이고, 다른 종류는 `failed` + `unsupported_branching` — 조용히
하나를 고르지 않습니다.

**노드 출력과 `CONDITION`(P4-2b, 개정 4, D-8, D-9).** `AGENT` 노드가 마치면 자식 Run 의 마지막
assistant 본문과 종결 상태를 `{"text", "status"}` 로 상한(`output_max_bytes`, 직렬화된 바이트)까지
잘라 `finish_node` 로 **함께** 기록합니다(잘렸으면 `output_truncated` 도). `START`·`END`·`CONDITION`
은 출력이 없습니다. `CONDITION` 은 선언된 맥락(`input` 과 지난 노드들의 출력)을 만들어 `domain` 의
순수 함수로 판정하고, 결과(`"true"`/`"false"`)와 같은 `label` 의 간선으로 갑니다. 판정할 수 없으면
(`condition_path_missing`·`condition_type_mismatch`) 노드와 Workflow 가 그 사유로 실패합니다.
**출력을 읽는 곳은 `_condition_context` 하나**이고, 출력은 이벤트·통지·로그·span 어디에도 넘기지
않습니다(C-3, `tests/arch/test_workflow_output_stays_in_data.py` 가 고정).

**`AGENT` 노드와 파킹(P4-2a B2).** 새 실행이면 Agent Version 을 해석하고(없으면 노드 실패
`agent_version_not_found`, 요청자가 없으면 `workflow_run_without_requester`), 자식 Run 의 id 를
**새로 정해 노드 실행 행에 영속(`park_node`)한 뒤에** `AgentRunLauncher.launch` 로 발사하고,
`waiting_run` 으로 **파킹**합니다 — 상태와 기다리는 대상만 남기고 호출은 끝나며 lease 는 `finally`
에서 놓입니다(R-7).
순서가 반대면 재전달에서 id 를 다시 만들어 자식 Run 이 둘이 됩니다(R-8). 깨우는 신호(자식 종결 통지·
스위퍼)는 어느 쪽이든 이 유스케이스를 **다시 부르는 것** 하나이고 판정은 여기서 합니다: 자식이 아직
종결이 아니면 **아무 것도 바꾸지 않고**(이벤트·통지·`seq` 증가 없음) 파킹을 유지한 채 돌아갑니다 —
그래서 같은 신호가 두 번 와도 전진은 한 번입니다. 노드 출력은 이 단위가 만들지 않습니다(D-8, P4-2b).

**순서.** 선언 읽기(없으면 `RuntimeError`, lease 도 잡지 않음) → `acquire_lease`(실패면
`WorkflowLeaseHeld`) → `load`(종결이면 아무것도 하지 않고 그 상태를 돌려줌 — 멱등) → 파킹 중이고
자식이
아직 종결이 아니면 그대로 돌아감 → `queued`/`waiting_run → running` → 현재 노드(없으면 `START`)부터
간선을 따라 전진 → `release`.

**멱등·재개의 축은 `start_node`.** `None` 은 "이미 기록돼 있다" 입니다(R-6, R-8). 이 경우 노드를
**다시 실행하지 않고** 기록이 `running` 으로 남아 있으면(시작만 하고 죽음) 새 행 없이 마무리하고,
이미 마쳤으면 건너뜁니다. `START`·`END` 는 실행할 것이 없어 "마무리" 가 곧 실행의 전부이고, `AGENT`
는 같은 축 위에서
`waiting_run` 기록(자식 id 가 영속된 상태)을 재개의 근거로 씁니다.

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

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from aether_runtime.domain.run import RunStatus, is_terminal

from aether_workflow.application.ports.inbound.advance_workflow_run import WorkflowLeaseHeld
from aether_workflow.application.ports.outbound.agent_run_launcher import (
    AgentRunLaunch,
    AgentRunLauncher,
)
from aether_workflow.application.ports.outbound.agent_run_reader import (
    AgentRunReader,
    AgentVersionRef,
)
from aether_workflow.application.ports.outbound.approval_reader import ApprovalReader
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
from aether_workflow.domain.condition import ConditionFailure, evaluate_condition
from aether_workflow.domain.events import (
    ApprovalGrantedPayload,
    ApprovalRequestedPayload,
    NodeFinishedPayload,
    NodeStartedPayload,
    WorkflowEvent,
    WorkflowEventType,
    WorkflowFinishedPayload,
    WorkflowStatusPayload,
)
from aether_workflow.domain.failure import WorkflowFailureReason
from aether_workflow.domain.node import Node, NodeKind
from aether_workflow.domain.node_execution import NodeExecutionRecord, NodeExecutionStatus
from aether_workflow.domain.node_output import agent_output
from aether_workflow.domain.run_execution import WorkflowRunExecution
from aether_workflow.domain.run_status import (
    TERMINAL_STATUSES,
    IllegalWorkflowTransition,
    WorkflowRunStatus,
    can_transition,
)

_FIRST_ITERATION = 0
_APPROVAL_KINDS = frozenset({NodeKind.HUMAN, NodeKind.APPROVAL})
_SUPPORTED_KINDS = frozenset(
    {NodeKind.START, NodeKind.END, NodeKind.AGENT, NodeKind.CONDITION} | _APPROVAL_KINDS
)
_BRANCH_LABELS = {True: "true", False: "false"}


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
        agent_runs: AgentRunReader,
        approvals: ApprovalReader,
        launcher: AgentRunLauncher,
        owner: str,
        lease_ttl_seconds: float,
        output_max_bytes: int = 8192,
    ) -> None:
        self._output_max_bytes = output_max_bytes
        self._store = store
        self._reader = reader
        self._sink = sink
        self._notifier = notifier
        self._clock = clock
        self._agent_runs = agent_runs
        self._approvals = approvals
        self._launcher = launcher
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
        if execution.status is WorkflowRunStatus.WAITING_RUN and self._still_waiting(execution):
            # 깨우는 신호가 왔지만 자식이 아직 종결이 아니다(중복 신호, 이른 신호) - 아무 것도
            # 바꾸지
            # 않는다. 이것이 R-8 의 핵심이다: 이벤트·통지·`seq` 증가가 없다.
            return WorkflowRunStatus.WAITING_RUN
        if execution.status is WorkflowRunStatus.WAITING_APPROVAL and not self._approval_is_stored(
            execution
        ):
            # 재큐 메시지는 승인이 아니다(R-12). 저장된 승인이 없으면 아무 것도 바꾸지 않는다 -
            # 이벤트·통지·`seq` 증가가 없다(R-8).
            return WorkflowRunStatus.WAITING_APPROVAL

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
            branch: bool | None = None
            if node.kind is NodeKind.AGENT:
                parked_or_failed = self._run_agent_node(cursor, node, declaration)
                if parked_or_failed is not None:
                    return parked_or_failed
            elif node.kind in _APPROVAL_KINDS:
                parked_or_failed = self._run_approval_node(cursor, node)
                if parked_or_failed is not None:
                    return parked_or_failed
            elif node.kind is NodeKind.CONDITION:
                decided = self._run_condition_node(cursor, node, declaration)
                if isinstance(decided, WorkflowRunStatus):
                    return decided
                branch = decided
            else:
                self._run_node(cursor, node)
            if node.kind is NodeKind.END:
                return self._finish(cursor, WorkflowRunStatus.SUCCEEDED, node_id=node.id)

            outgoing = [e for e in declaration.edges if e.source == node.id]
            if branch is not None:
                label = _BRANCH_LABELS[branch]
                chosen = [e for e in outgoing if e.label == label]
                following = nodes.get(chosen[0].target) if chosen else None
            elif len(outgoing) > 1:
                return self._finish(
                    cursor,
                    WorkflowRunStatus.FAILED,
                    WorkflowFailureReason.UNSUPPORTED_BRANCHING,
                    node_id=node.id,
                )
            else:
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

    # -- CONDITION ------------------------------------------------------------

    def _run_condition_node(
        self, cursor: _Cursor, node: Node, declaration: WorkflowRunDeclaration
    ) -> bool | WorkflowRunStatus:
        """판정 결과(`True` -> `"true"` 분기)를 돌려줍니다. 판정할 수 없으면 노드와 Workflow 가
        실패하고 그 종결 상태를 돌려줍니다. 판정은 순수 함수에 맥락이 같으면 결과가 같으므로,
        노드를 마친 뒤 죽은 재개는 **다시 판정해** 같은 분기로 갑니다(분기를 영속하지 않습니다)."""
        run_id = cursor.workflow_run_id
        node_execution_id = self._store.start_node(run_id, node.id, _FIRST_ITERATION)
        already_finished = False
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
            record = self._record(run_id, node.id)
            if record is None:
                raise RuntimeError(f"node {node.id} of {run_id} is recorded but not readable")
            if record.status is NodeExecutionStatus.FAILED:
                reason = (
                    WorkflowFailureReason(record.failure_reason)
                    if record.failure_reason is not None
                    else WorkflowFailureReason.INVALID_GRAPH
                )
                return self._finish(cursor, WorkflowRunStatus.FAILED, reason, node_id=node.id)
            node_execution_id = record.id
            already_finished = record.status is NodeExecutionStatus.SUCCEEDED

        try:
            if node.condition_path is None or node.condition_operator is None:
                raise ConditionFailure(WorkflowFailureReason.INVALID_GRAPH)
            result = evaluate_condition(
                self._condition_context(declaration),
                node.condition_path,
                node.condition_operator,
                node.condition_value,
            )
        except ConditionFailure as failure:
            if already_finished:
                return self._finish(
                    cursor, WorkflowRunStatus.FAILED, failure.reason, node_id=node.id
                )
            return self._fail_node(cursor, node, node_execution_id, failure.reason)

        if not already_finished:
            self._store.finish_node(
                node_execution_id, NodeExecutionStatus.SUCCEEDED, self._clock.now()
            )
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
        return result

    def _condition_context(self, declaration: WorkflowRunDeclaration) -> dict[str, Any]:
        """판정 대상이 되는 **선언된 맥락 하나**(spec 개정 4 (1)). 노드의 출력을 읽는 곳은 제품에서
        여기뿐입니다(C-3) - 세 번째 소비자를 만들지 않습니다."""
        outputs: dict[str, Any] = {}
        records = sorted(
            self._store.node_executions(declaration.workflow_run_id), key=lambda r: r.iteration
        )
        for record in records:
            if record.output is not None:
                outputs[record.node_id] = record.output
        return {"input": declaration.input, "nodes": outputs}

    # -- HUMAN / APPROVAL 노드와 승인 대기 -----------------------------------------

    def _approval_is_stored(self, execution: WorkflowRunExecution) -> bool:
        """`waiting_approval` 인 Workflow Run 이 기다리는 노드 실행에 **저장된 승인** 이 있는가.
        기다리는 노드 실행을 알 수 없으면(포인터 없음) 승인을 증명할 수 없으므로 `False` - 멈춘 채로
        둡니다(fail-closed). 이 판정에 재큐 메시지는 관여하지 않습니다."""
        awaited = execution.waiting_node_execution_id
        if awaited is None:
            return False
        return self._approvals.approval_for(awaited) is not None

    def _run_approval_node(self, cursor: _Cursor, node: Node) -> WorkflowRunStatus | None:
        """`HUMAN` 과 `APPROVAL` 은 v1 에서 **같다**(spec 2.6 개정 5 (5)). `None` 이면 승인이 저장돼
        노드를 마쳤으니 다음으로 갑니다. 아니면 이 호출이 끝나는 상태(`waiting_approval`
        파킹)입니다.

        여기에 "누가 승인했는가" 를 묻는 코드는 없습니다 - 권한 모델은 만들지 않습니다(C-4)."""
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
            return self._park_for_approval(cursor, node, node_execution_id)

        # 이미 기록돼 있다 - 새 실행이 아니라 재개입니다(R-6, R-8).
        record = self._record(run_id, node.id)
        if record is None:
            raise RuntimeError(f"node {node.id} of {run_id} is recorded but not readable")
        if record.status is NodeExecutionStatus.SUCCEEDED:
            return None
        if record.status is NodeExecutionStatus.FAILED:
            reason = (
                WorkflowFailureReason(record.failure_reason)
                if record.failure_reason is not None
                else WorkflowFailureReason.INVALID_GRAPH
            )
            return self._finish(cursor, WorkflowRunStatus.FAILED, reason, node_id=node.id)
        # `running`(시작만 하고 죽음) 또는 `waiting_approval`: 저장된 승인이 있어야만 마친다. 상태
        # 쪽 검사(`_approval_is_stored`)를 지난 뒤에도 노드 쪽에서 한 번 더 묻는 이유는, 상태를
        # 저장하기 전에 죽은 재전달도 같은 규칙으로 판정하기 위해서다.
        if self._approvals.approval_for(record.id) is None:
            return self._park_for_approval(cursor, node, record.id)

        self._store.finish_node(record.id, NodeExecutionStatus.SUCCEEDED, self._clock.now())
        self._emit_node_event(
            cursor,
            "approval.granted",
            ApprovalGrantedPayload(node_id=node.id, iteration=_FIRST_ITERATION).model_dump(),
            node.id,
        )
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
        return None

    def _park_for_approval(
        self, cursor: _Cursor, node: Node, node_execution_id: UUID
    ) -> WorkflowRunStatus:
        """`waiting_approval` 으로 내려갑니다: 노드를 대기로 표시하고, Workflow Run 상태와 기다리는
        노드 실행의 id 를 저장하고, 발행·통지하고, `approval.requested` 를 냅니다. lease 는 호출자의
        `finally` 가 놓습니다 - 대기 중에 쥐고 있으면 worker 슬롯을 점유합니다(R-7)."""
        if not can_transition(WorkflowRunStatus.RUNNING, WorkflowRunStatus.WAITING_APPROVAL):
            raise IllegalWorkflowTransition(
                WorkflowRunStatus.RUNNING, WorkflowRunStatus.WAITING_APPROVAL
            )
        self._store.park_node_for_approval(node_execution_id)
        now = self._clock.now()
        cursor.seq += 1
        cursor.node_id = node.id
        self._store.set_status(
            cursor.workflow_run_id,
            WorkflowRunStatus.WAITING_APPROVAL,
            seq=cursor.seq,
            current_node_id=node.id,
            waiting_node_execution_id=node_execution_id,
        )
        self._publish(
            cursor,
            "workflow.status",
            WorkflowStatusPayload(
                status=WorkflowRunStatus.WAITING_APPROVAL.value, current_node_id=node.id
            ).model_dump(exclude_none=True),
            now,
        )
        self._notifier.notify(
            WorkflowStatusMessage(
                workflow_run_id=cursor.workflow_run_id,
                seq=cursor.seq,
                status=WorkflowRunStatus.WAITING_APPROVAL,
                at=now,
                current_node_id=node.id,
                waiting_node_execution_id=node_execution_id,
            )
        )
        # 저장 먼저, 발행은 그 다음(모듈 docstring 의 `seq` 규칙). 이 `seq` 는 상태 통지가 없는
        # 이벤트의 것이라 투영은 건너뛰고 이벤트 스트림만 앞선다 - 빈틈은 단조성을 해치지 않는다.
        cursor.seq += 1
        self._store.set_status(
            cursor.workflow_run_id,
            WorkflowRunStatus.WAITING_APPROVAL,
            seq=cursor.seq,
            current_node_id=node.id,
        )
        self._publish(
            cursor,
            "approval.requested",
            ApprovalRequestedPayload(node_id=node.id, iteration=_FIRST_ITERATION).model_dump(),
            now,
        )
        return WorkflowRunStatus.WAITING_APPROVAL

    # -- AGENT 노드와 파킹 -----------------------------------------------------

    def _record(self, run_id: UUID, node_id: str) -> NodeExecutionRecord | None:
        return next(
            (
                r
                for r in self._store.node_executions(run_id)
                if r.node_id == node_id and r.iteration == _FIRST_ITERATION
            ),
            None,
        )

    def _still_waiting(self, execution: WorkflowRunExecution) -> bool:
        """파킹 중인 Workflow 의 자식 Run 이 아직 종결이 아니면 `True`. 자식의 실행 행이 없는 것
        (`None`, 아직 worker 가 집지 않음)도 종결이 아닙니다. 기록이 어긋나 판단할 수 없으면
        `False` 로 두어 전진 경로가 기록을 보고 판정하게 합니다."""
        if execution.current_node_id is None:
            return False
        record = self._record(execution.workflow_run_id, execution.current_node_id)
        if (
            record is None
            or record.status is not NodeExecutionStatus.WAITING_RUN
            or record.agent_run_id is None
        ):
            return False
        child = self._agent_runs.status(record.agent_run_id)
        return child is None or not is_terminal(child)

    def _run_agent_node(
        self, cursor: _Cursor, node: Node, declaration: WorkflowRunDeclaration
    ) -> WorkflowRunStatus | None:
        """`None` 이면 노드를 마쳤으니 다음으로 갑니다. 아니면 이 호출이 끝나는 상태(`waiting_run`
        파킹 또는 종결)입니다."""
        run_id = cursor.workflow_run_id
        node_execution_id = self._store.start_node(run_id, node.id, _FIRST_ITERATION)
        agent_run_id: UUID | None = None
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
            # 이미 기록돼 있다 - 새 실행이 아니라 재개입니다(R-6, R-8).
            record = self._record(run_id, node.id)
            if record is None:
                raise RuntimeError(f"node {node.id} of {run_id} is recorded but not readable")
            if record.status is NodeExecutionStatus.SUCCEEDED:
                return None
            if record.status is NodeExecutionStatus.FAILED:
                # 노드는 실패로 마쳤는데 Workflow 를 끝내기 전에 죽었다 - 남은 사유로 마저 끝낸다.
                reason = (
                    WorkflowFailureReason(record.failure_reason)
                    if record.failure_reason is not None
                    else WorkflowFailureReason.AGENT_RUN_FAILED
                )
                return self._finish(cursor, WorkflowRunStatus.FAILED, reason, node_id=node.id)
            node_execution_id = record.id
            agent_run_id = record.agent_run_id

        if agent_run_id is None:
            # 새 실행(또는 id 를 영속하기 전에 죽은 재개): 해석 -> **영속** -> 발사 -> 파킹.
            resolved = self._resolve(declaration, node)
            if isinstance(resolved, WorkflowFailureReason):
                return self._fail_node(cursor, node, node_execution_id, resolved)
            agent_run_id = uuid4()
            self._store.park_node(node_execution_id, agent_run_id)
            self._launch(declaration, agent_run_id, resolved)
            return self._park(cursor, node, agent_run_id)

        child = self._agent_runs.status(agent_run_id)
        if child is None or not is_terminal(child):
            if child is None:
                # id 는 영속됐지만 발사했는지 모른다(영속과 파킹 사이에서 죽었을 수 있다). 같은 id
                # 로 다시 발사한다 - api 쪽 선언이 멱등이라 자식 Run 은 하나다.
                resolved = self._resolve(declaration, node)
                if isinstance(resolved, WorkflowFailureReason):
                    return self._fail_node(cursor, node, node_execution_id, resolved)
                self._launch(declaration, agent_run_id, resolved)
            return self._park(cursor, node, agent_run_id)

        succeeded = child is RunStatus.SUCCEEDED
        node_status = NodeExecutionStatus.SUCCEEDED if succeeded else NodeExecutionStatus.FAILED
        node_reason = None if succeeded else WorkflowFailureReason.AGENT_RUN_FAILED
        output = agent_output(
            self._agent_runs.last_assistant_text(agent_run_id) or "",
            child.value,
            self._output_max_bytes,
        )
        self._store.finish_node(
            node_execution_id, node_status, self._clock.now(), node_reason, output
        )
        self._emit_node_event(
            cursor,
            "node.finished",
            NodeFinishedPayload(
                node_id=node.id, iteration=_FIRST_ITERATION, status=node_status.value
            ).model_dump(),
            node.id,
        )
        if succeeded:
            return None
        return self._finish(
            cursor,
            WorkflowRunStatus.FAILED,
            WorkflowFailureReason.AGENT_RUN_FAILED,
            node_id=node.id,
        )

    def _resolve(
        self, declaration: WorkflowRunDeclaration, node: Node
    ) -> AgentVersionRef | WorkflowFailureReason:
        """발사에 필요한 것을 모읍니다. 하나라도 없으면 **발사하지 않고** 사유를 돌려줍니다 -
        발사하면
        api 가 선언하지 못한 자식을 기다리며 영원히 파킹됩니다(`2026-10-11-001`)."""
        if declaration.requested_by is None:
            return WorkflowFailureReason.WORKFLOW_RUN_WITHOUT_REQUESTER
        if node.agent_id is None:
            return WorkflowFailureReason.AGENT_VERSION_NOT_FOUND
        ref = self._agent_runs.version_for(node.agent_id, node.agent_version)
        if ref is None:
            return WorkflowFailureReason.AGENT_VERSION_NOT_FOUND
        return ref

    def _launch(
        self, declaration: WorkflowRunDeclaration, agent_run_id: UUID, ref: AgentVersionRef
    ) -> None:
        requested_by = declaration.requested_by
        if requested_by is None:  # _resolve 가 이미 걸렀다 - 타입 좁히기
            raise RuntimeError("launch without requester")
        self._launcher.launch(
            AgentRunLaunch(
                agent_run_id=agent_run_id,
                agent_version_id=ref.agent_version_id,
                input=_serialize_input(declaration.input),
                requested_by=requested_by,
                traceparent=None,
            )
        )

    def _park(self, cursor: _Cursor, node: Node, agent_run_id: UUID) -> WorkflowRunStatus:
        """`waiting_run` 으로 내려갑니다: 저장하고, 발행하고, 통지합니다. lease 는 호출자의
        `finally` 가 놓습니다 - 대기 중에 쥐고 있으면 worker 슬롯을 점유합니다(R-7)."""
        if not can_transition(WorkflowRunStatus.RUNNING, WorkflowRunStatus.WAITING_RUN):
            raise IllegalWorkflowTransition(
                WorkflowRunStatus.RUNNING, WorkflowRunStatus.WAITING_RUN
            )
        now = self._clock.now()
        cursor.seq += 1
        cursor.node_id = node.id
        self._store.set_status(
            cursor.workflow_run_id,
            WorkflowRunStatus.WAITING_RUN,
            seq=cursor.seq,
            current_node_id=node.id,
            waiting_run_id=agent_run_id,
        )
        self._publish(
            cursor,
            "workflow.status",
            WorkflowStatusPayload(
                status=WorkflowRunStatus.WAITING_RUN.value, current_node_id=node.id
            ).model_dump(exclude_none=True),
            now,
        )
        self._notifier.notify(
            WorkflowStatusMessage(
                workflow_run_id=cursor.workflow_run_id,
                seq=cursor.seq,
                status=WorkflowRunStatus.WAITING_RUN,
                at=now,
                current_node_id=node.id,
                waiting_run_id=agent_run_id,
            )
        )
        return WorkflowRunStatus.WAITING_RUN

    def _fail_node(
        self,
        cursor: _Cursor,
        node: Node,
        node_execution_id: UUID,
        reason: WorkflowFailureReason,
    ) -> WorkflowRunStatus:
        self._store.finish_node(
            node_execution_id, NodeExecutionStatus.FAILED, self._clock.now(), reason
        )
        self._emit_node_event(
            cursor,
            "node.finished",
            NodeFinishedPayload(
                node_id=node.id,
                iteration=_FIRST_ITERATION,
                status=NodeExecutionStatus.FAILED.value,
            ).model_dump(),
            node.id,
        )
        return self._finish(cursor, WorkflowRunStatus.FAILED, reason, node_id=node.id)

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


def _serialize_input(value: dict[str, object] | None) -> str:
    """자식 Run 의 입력 - Workflow Run 의 `input` 을 직렬화한 것(spec 0005 2.5 개정 3). 정렬된
    compact JSON 이라 같은 입력은 같은 문자열입니다. 입력이 없으면 빈 문자열."""
    if value is None:
        return ""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
