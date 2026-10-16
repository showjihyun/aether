"""spec 0005 2.1, 2.3, 2.9 개정 2, 2.10, R-6, R-8, D-13 (P4-2a A): `AdvanceWorkflowRunUseCase` —
Workflow Run 을 `START` 에서 `END` 까지 전진시키는 실행기 골격. `AdvanceWorkflowRun`(inbound
포트)의 유일한 구현입니다.

**범위.** 지원하는 노드 종류는 `START`·`END`·`AGENT`·`CONDITION`·`HUMAN`·`APPROVAL`·`PARALLEL`·
`JOIN`·`LOOP`·`WAIT` 열입니다(`HUMAN`·`APPROVAL` 은 v1 에서 같게 `waiting_approval` 로 파킹합니다,
P4-4).
나머지 종류를 만나면 `failed` + `unsupported_node_kind` 로 끝납니다(절반만 만든 노드를 두지
않습니다).
나가는 간선이 둘 이상인 노드는 `CONDITION`·`LOOP`·`PARALLEL` 만 예외이고, 다른 종류는 `failed` +
`unsupported_branching` - 조용히 하나를 고르지 않습니다.

**진행은 노드 실행 기록에서 읽습니다(spec 0005 2.7 개정 7 (2)).** 전진할 수 있는 노드는 들어오는
간선의 출발 노드가 모두 마친(그리고 `CONDITION`·`LOOP` 이 고른) 노드이고, 그 유도는
`domain.progress`
의 순수 함수가 합니다. **`current_node_id` 는 "마지막으로 전진한 노드" 입니다**(관측용 - 투영과
이벤트가
보는 값이고 전진의 근거가 아닙니다). 재개한 호출은 기록에서 이미 시작한 노드(파킹 중이던 노드)를
먼저,
그다음 새로 전진할 수 있는 노드를 선언 순서로 하나씩 실행합니다. `PARALLEL` 의 분기는 **차례로**
실행됩니다(동시성 없음, 개정 7 (1)) - 분기 안의 파킹은 Run 전체를 파킹하고 재개 때 남은 분기를
잇습니다.

**`PARALLEL`·`JOIN`(R-9).** 분기 안의 노드가 실패하면 그 자리에서 Workflow 를 끝내지 않고 노드만
`failed` 로 남깁니다(그 하류는 막힙니다). 다른 분기를 마저 돌린 뒤 `JOIN` 이 분기별
출력(`{"branches":
{...}}`, 상한과 잘림 표시는 `node_output.join_output`)과 함께 `failed` + `branch_failed` 로 기록하고
Workflow 를 끝냅니다. 분기 밖의 실패는 그 노드의 사유로 즉시 끝납니다.

**`LOOP`(R-10).** `CONDITION` 과 같은 판정식이고 `true` 간선이 본문, `false` 가 탈출입니다. 회차는
`iteration` 입니다 - `LOOP` 노드의 기록은 판정마다 한 행, 본문 노드는 한 바퀴마다 `iteration` 이 1
늘어납니다. 판정이 참인데 이미 `max_iterations` 번 돌았으면(`iteration >= max_iterations`)
본문을 한 번
더 돌리지 않고 `failed` + `loop_limit_exceeded` 로 끝납니다.

**노드 출력과 `CONDITION`(P4-2b, 개정 4, D-8, D-9).** `AGENT` 노드가 마치면 자식 Run 의 마지막
assistant 본문과 종결 상태를 `{"text", "status"}` 로 상한(`output_max_bytes`, 직렬화된 바이트)까지
잘라 `finish_node` 로 **함께** 기록합니다(잘렸으면 `output_truncated` 도). `START`·`END`·`CONDITION`
은 출력이 없습니다. `CONDITION` 은 선언된 맥락(`input` 과 지난 노드들의 출력)을 만들어 `domain` 의
순수 함수로 판정하고, 결과(`"true"`/`"false"`)와 같은 `label` 의 간선으로 갑니다. 판정할 수 없으면
(`condition_path_missing`·`condition_type_mismatch`) 노드와 Workflow 가 그 사유로 실패합니다.
**출력을 읽는 곳은 `_condition_context` 하나**이고, 출력은 이벤트·통지·로그·span 어디에도 넘기지
않습니다(C-3, `tests/arch/test_workflow_output_stays_in_data.py` 가 고정).

**`WAIT`(R-11, 개정 7 (5)).** 실제 시간을 블록하지 않고(D-4) **파킹**합니다: 노드 실행을 시작하고
`wake_at = clock.now() + wait_seconds` 를 정해 Workflow Run 을 `waiting_timer` + `wake_at` 으로
파킹합니다(노드 실행도 `waiting_timer`). 이벤트는 기존 `workflow.status` 하나입니다. 깨우는 외부
사건이
없으므로 **스위퍼가 주 경로**입니다 - `wake_at` 이 지난 건을 스위퍼가 주워 이 유스케이스를 다시
부릅니다. 재개한 호출은 `clock.now() >= wake_at` 일 때만 노드를 마치고 다음으로 갑니다. 아직이면
**아무 것도 바꾸지 않고**(이벤트·통지·`seq` 증가 없음) 파킹을 유지합니다. 시계는 주입된 `Clock` 이고
이 모듈은 어떤 대기 호출도 하지 않습니다(R-11).

**`LLM`·`TOOL`·`MCP`(P4-5, 개정 9, R-14).** 세 종류는 **파킹하지 않고** 한 번 부르고 끝납니다
(자식 Run 이 없습니다). 모델은 `ModelInvoker`, 도구는 `ToolInvoker` 포트만 지납니다(AR-5·AR-6 -
이 모듈은 게이트웨이도 SDK 도 모릅니다, 조립은 worker 의 `main`). 프롬프트·인자는
`_condition_context` 의 같은 맥락에서 `domain.node_input` 이 조립합니다(경로가 없으면
`condition_path_missing`, 인자 경로가 객체가 아니면 `condition_type_mismatch` - 호출 **전에**
실패). `TOOL`·`MCP` 는 `agent_id` 의 Version 으로 권한을 행사합니다(`version_for`, 없으면
`agent_version_not_found`). 거부는 `tool_call_denied`, 호출 실패·`is_error` 는
`tool_call_failed`, 모델 예외는 `model_call_failed` - 모두 노드와 Workflow 를 실패시킵니다.
출력은 `{"text","finish_reason"}`·`{"content","is_error"}` 이고 `AGENT` 와 같은 상한을 받습니다.
**재전달**: 시작만 하고 죽은 노드(`running`)는 다시 부릅니다(at-least-once - 모델 호출은 부수 효과가
없지만 도구는 있을 수 있습니다). 이미 마친 노드는 다시 부르지 않습니다. 포트가 꽂히지 않은 종류는
`unsupported_node_kind` 입니다.

**`AGENT` 노드와 파킹(P4-2a B2).** 새 실행이면 Agent Version 을 해석하고(없으면 노드 실패
`agent_version_not_found`, 요청자가 없으면 `workflow_run_without_requester`), 자식 Run 의 id 를
**새로 정해 노드 실행 행에 영속(`park_node`)한 뒤에** `AgentRunLauncher.launch` 로 발사하고,
`waiting_run` 으로 **파킹**합니다 — 상태와 기다리는 대상만 남기고 호출은 끝납니다. lease 는 파킹이
이벤트·통지보다 **먼저** 놓고(개정 8 (2)) `finally` 에서 한 번 더 놓습니다(R-7).
순서가 반대면 재전달에서 id 를 다시 만들어 자식 Run 이 둘이 됩니다(R-8). 깨우는 신호(자식 종결 통지·
스위퍼)는 어느 쪽이든 이 유스케이스를 **다시 부르는 것** 하나이고 판정은 여기서 합니다: 자식이 아직
종결이 아니면 **아무 것도 바꾸지 않고**(이벤트·통지·`seq` 증가 없음) 파킹을 유지한 채 돌아갑니다 —
그래서 같은 신호가 두 번 와도 전진은 한 번입니다. 노드 출력은 이 단위가 만들지 않습니다(D-8, P4-2b).

**순서.** 선언 읽기(없으면 `RuntimeError`, lease 도 잡지 않음) → `acquire_lease`(실패면
`WorkflowLeaseHeld`) → `load`(종결이면 아무것도 하지 않고 그 상태를 돌려줌 — 멱등) → 파킹 중이고
자식이
아직 종결이 아니면 그대로 돌아감 → `queued`/`waiting_run → running` → 기록에서 전진할 수 있는 노드를
하나씩 실행(없으면 종결 판정) → `release`.

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
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
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
from aether_workflow.application.ports.outbound.model_invoker import ModelInvoker
from aether_workflow.application.ports.outbound.tool_invoker import (
    ToolInvocationDenied,
    ToolInvoker,
)
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
from aether_workflow.domain.condition import (
    ConditionFailure,
    evaluate_condition,
    points_at_unrecorded_node,
)
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
from aether_workflow.domain.node_input import build_arguments, build_prompt
from aether_workflow.domain.node_output import (
    NodeOutput,
    agent_output,
    join_output,
    llm_output,
    tool_output,
)
from aether_workflow.domain.progress import Progress, branch_members
from aether_workflow.domain.run_execution import WorkflowRunExecution
from aether_workflow.domain.run_status import (
    TERMINAL_STATUSES,
    IllegalWorkflowTransition,
    WorkflowRunStatus,
    can_transition,
)

_APPROVAL_KINDS = frozenset({NodeKind.HUMAN, NodeKind.APPROVAL})
_BRANCHING_KINDS = frozenset({NodeKind.CONDITION, NodeKind.LOOP, NodeKind.PARALLEL})
_TOOL_KINDS = frozenset({NodeKind.TOOL, NodeKind.MCP})
_SUPPORTED_KINDS = frozenset(
    {
        NodeKind.START,
        NodeKind.END,
        NodeKind.AGENT,
        NodeKind.CONDITION,
        NodeKind.PARALLEL,
        NodeKind.JOIN,
        NodeKind.LOOP,
        NodeKind.WAIT,
    }
    | _APPROVAL_KINDS
)


@dataclass
class _Cursor:
    """한 번의 전진 동안의 가변 위치 — `seq` 와 마지막으로 전진한 노드(`node_id`).

    `node_id` 는 관측용입니다(`current_node_id` 로 저장됩니다) - 전진의 근거가 아닙니다.
    `contained` 는 `PARALLEL` 분기 안의 노드들로, 이 노드의 실패는 `JOIN` 이 관측합니다(R-9).
    """

    workflow_run_id: UUID
    seq: int
    node_id: str | None
    contained: frozenset[str] = frozenset()
    wake_at: datetime | None = None
    """이 호출이 `waiting_timer` 에서 깨어났다면 그때 저장돼 있던 `wake_at`(`_to_running` 이 저장소
    의 값을 지우기 전의 것). `WAIT` 노드의 재개 판정이 읽는다."""


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
        models: ModelInvoker | None = None,
        tools: ToolInvoker | None = None,
    ) -> None:
        self._output_max_bytes = output_max_bytes
        self._models = models
        self._tools = tools
        self._supported_kinds = (
            _SUPPORTED_KINDS
            | (frozenset({NodeKind.LLM}) if models is not None else frozenset())
            | (_TOOL_KINDS if tools is not None else frozenset())
        )
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

    def _release_before_announcing(self, cursor: _Cursor) -> None:
        """파킹의 순서는 **상태 저장 -> lease 해제 -> 이벤트·통지**입니다(spec 0005 2.5 개정 8 (2)).
        발행·통지를 먼저 하고 lease 를 `__call__` 의 `finally` 에서 놓으면, 관찰자가 "상태는
        대기인데
        lease 는 아직 잡힌" 창을 실제로 봅니다. 여기서 놓아도 `finally` 의 `release` 는 그대로
        불립니다 - 같은 owner 조건부 UPDATE(`WHERE lease_owner = owner`)라 두 번째는 아무 행도
        바꾸지 않아 두 번 불러도 무해합니다. **파킹에만** 적용합니다: 종결(`_finish`)은 종결 한 쌍을
        먼저 내고 상태를 마지막에 저장하는 순서가 따로 있어 그대로 둡니다."""
        self._store.release(cursor.workflow_run_id, self._owner)

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
        if execution.status is WorkflowRunStatus.WAITING_TIMER and not self._timer_elapsed(
            execution.wake_at
        ):
            # 깨움이 `wake_at` 보다 일찍 왔다(중복·이른 재큐) - 아무 것도 바꾸지 않는다(R-8).
            return WorkflowRunStatus.WAITING_TIMER

        cursor = _Cursor(
            run_id,
            execution.status_seq,
            execution.current_node_id,
            branch_members(declaration.nodes, declaration.edges),
            wake_at=(
                execution.wake_at if execution.status is WorkflowRunStatus.WAITING_TIMER else None
            ),
        )
        if execution.status is not WorkflowRunStatus.RUNNING:
            self._to_running(cursor, execution.status, first_start=execution.started_at is None)

        if not any(n.kind is NodeKind.START for n in declaration.nodes):
            return self._finish(
                cursor, WorkflowRunStatus.FAILED, WorkflowFailureReason.INVALID_GRAPH
            )

        previous: tuple[str, int] | None = None
        while True:
            records = self._store.node_executions(run_id)
            progress = Progress(
                declaration.nodes, declaration.edges, records, self._decider(declaration)
            )
            settled = self._settle(cursor, declaration, records, progress)
            if settled is not None:
                return settled
            ready = progress.next_ready()
            if ready is None:
                return self._stuck(cursor, records)
            node, iteration = ready
            if (node.id, iteration) == previous:
                # 방금 실행한 인스턴스가 또 전진 가능하다 - 기록이 진행을 반영하지 않는다는 뜻이다.
                raise RuntimeError(f"node {node.id}#{iteration} of {run_id} did not advance")
            previous = (node.id, iteration)
            finished = self._execute(cursor, node, iteration, declaration, progress)
            if finished is not None:
                return finished

    def _decider(self, declaration: WorkflowRunDeclaration) -> Callable[[Node], bool | None]:
        """`CONDITION`·`LOOP` 의 판정식을 지금 맥락으로 평가한다 - 판정할 수 없으면 `None`."""

        def decide(node: Node) -> bool | None:
            try:
                return self._judge(declaration, node)
            except ConditionFailure:
                return None

        return decide

    def _settle(
        self,
        cursor: _Cursor,
        declaration: WorkflowRunDeclaration,
        records: tuple[NodeExecutionRecord, ...],
        progress: Progress,
    ) -> WorkflowRunStatus | None:
        """기록이 이미 Workflow 의 끝을 말하고 있으면 그 끝으로 끝낸다 - `END` 를 마쳤거나, 분기 밖
        노드가 실패했거나, 마친 노드의 나가는 간선이 그 종류가 허락하지 않는 모양이다. 새로 실행했을
        때와 죽었다 깨어난 재전달이 같은 길을 지난다."""
        succeeded = {r.node_id for r in records if r.status is NodeExecutionStatus.SUCCEEDED}
        for node in declaration.nodes:
            if node.kind is NodeKind.END and node.id in succeeded:
                return self._finish(cursor, WorkflowRunStatus.SUCCEEDED, node_id=node.id)
        for record in records:
            if record.status is NodeExecutionStatus.FAILED and (
                record.node_id not in cursor.contained
                or record.failure_reason == WorkflowFailureReason.LOOP_LIMIT_EXCEEDED.value
            ):
                reason = (
                    WorkflowFailureReason(record.failure_reason)
                    if record.failure_reason is not None
                    else WorkflowFailureReason.INVALID_GRAPH
                )
                return self._finish(
                    cursor, WorkflowRunStatus.FAILED, reason, node_id=record.node_id
                )
        for node in declaration.nodes:
            if node.id not in succeeded:
                continue
            count = progress.outgoing_count(node.id)
            if count == 0:
                return self._finish(
                    cursor,
                    WorkflowRunStatus.FAILED,
                    WorkflowFailureReason.INVALID_GRAPH,
                    node_id=node.id,
                )
            if count > 1 and node.kind not in _BRANCHING_KINDS:
                return self._finish(
                    cursor,
                    WorkflowRunStatus.FAILED,
                    WorkflowFailureReason.UNSUPPORTED_BRANCHING,
                    node_id=node.id,
                )
        return None

    def _stuck(
        self, cursor: _Cursor, records: tuple[NodeExecutionRecord, ...]
    ) -> WorkflowRunStatus:
        """전진할 노드가 없는데 끝나지 않았다. 분기 안의 실패가 `JOIN` 에 닿지 못했으면 그 사유로,
        아니면(고른 분기에 간선이 없는 등) 그래프가 잘못된 것이다."""
        failed = next((r for r in records if r.status is NodeExecutionStatus.FAILED), None)
        if failed is not None:
            reason = (
                WorkflowFailureReason(failed.failure_reason)
                if failed.failure_reason is not None
                else WorkflowFailureReason.INVALID_GRAPH
            )
            return self._finish(cursor, WorkflowRunStatus.FAILED, reason, node_id=failed.node_id)
        return self._finish(cursor, WorkflowRunStatus.FAILED, WorkflowFailureReason.INVALID_GRAPH)

    def _execute(
        self,
        cursor: _Cursor,
        node: Node,
        iteration: int,
        declaration: WorkflowRunDeclaration,
        progress: Progress,
    ) -> WorkflowRunStatus | None:
        """`None` 이면 노드를 마쳤으니(또는 분기 안에서 실패로 마쳤으니) 다음 노드로 간다. 아니면
        이 호출이 끝나는 상태(파킹 또는 종결)다."""
        if node.kind not in self._supported_kinds:
            return self._finish(
                cursor,
                WorkflowRunStatus.FAILED,
                WorkflowFailureReason.UNSUPPORTED_NODE_KIND,
                node_id=node.id,
            )
        if node.kind is NodeKind.AGENT:
            return self._run_agent_node(cursor, node, declaration, iteration)
        if node.kind is NodeKind.LLM or node.kind in _TOOL_KINDS:
            return self._run_invoke_node(cursor, node, declaration, iteration)
        if node.kind in _APPROVAL_KINDS:
            return self._run_approval_node(cursor, node, iteration)
        if node.kind in (NodeKind.CONDITION, NodeKind.LOOP):
            return self._run_condition_node(cursor, node, declaration, iteration)
        if node.kind is NodeKind.JOIN:
            return self._run_join_node(cursor, node, declaration, progress, iteration)
        if node.kind is NodeKind.WAIT:
            return self._run_wait_node(cursor, node, iteration)
        self._run_node(cursor, node, iteration)
        return None

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

    def _run_node(self, cursor: _Cursor, node: Node, iteration: int) -> None:
        """`START`·`END`·`PARALLEL` 은 실행할 것이 없어 기록의 시작과 마침이 실행의 전부입니다."""
        run_id = cursor.workflow_run_id
        node_execution_id = self._store.start_node(run_id, node.id, iteration)
        if node_execution_id is not None:
            self._emit_node_event(
                cursor,
                "node.started",
                NodeStartedPayload(
                    node_id=node.id, kind=node.kind.value, iteration=iteration
                ).model_dump(),
                node.id,
            )
        else:
            # 이미 기록돼 있다 - 다시 실행하지 않습니다(R-6, R-8).
            record = self._record(run_id, node.id, iteration)
            if record is None or record.status is not NodeExecutionStatus.RUNNING:
                return
            node_execution_id = record.id
        self._store.finish_node(node_execution_id, NodeExecutionStatus.SUCCEEDED, self._clock.now())
        self._emit_node_event(
            cursor,
            "node.finished",
            NodeFinishedPayload(
                node_id=node.id,
                iteration=iteration,
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
        self,
        cursor: _Cursor,
        node: Node,
        declaration: WorkflowRunDeclaration,
        iteration: int,
    ) -> WorkflowRunStatus | None:
        """`CONDITION` 과 `LOOP` 의 판정을 기록합니다. 어느 간선으로 갈지는 여기서 돌려주지
        않습니다 -
        진행은 기록에서 유도합니다(`domain.progress`). 판정할 수 없으면 노드와 Workflow 가
        실패합니다.
        판정은 순수 함수에 맥락이 같으면 결과가 같으므로, 노드를 마친 뒤 죽은 재개는 다시 판정해
        같은
        분기로 갑니다(분기를 영속하지 않습니다).

        `LOOP` 는 판정이 참인데 이미 `max_iterations` 번 돌았으면(`iteration` 이 그 수 이상) 본문을
        한 번 더 돌리지 않고 `loop_limit_exceeded` 로 실패합니다(R-10)."""
        run_id = cursor.workflow_run_id
        node_execution_id = self._store.start_node(run_id, node.id, iteration)
        if node_execution_id is not None:
            self._emit_node_event(
                cursor,
                "node.started",
                NodeStartedPayload(
                    node_id=node.id, kind=node.kind.value, iteration=iteration
                ).model_dump(),
                node.id,
            )
        else:
            record = self._record(run_id, node.id, iteration)
            if record is None:
                raise RuntimeError(f"node {node.id} of {run_id} is recorded but not readable")
            node_execution_id = record.id

        try:
            result = self._judge(declaration, node)
        except ConditionFailure as failure:
            return self._fail_node(cursor, node, node_execution_id, failure.reason, iteration)

        if node.kind is NodeKind.LOOP and result and iteration >= (node.max_iterations or 0):
            return self._fail_node(
                cursor,
                node,
                node_execution_id,
                WorkflowFailureReason.LOOP_LIMIT_EXCEEDED,
                iteration,
            )

        self._store.finish_node(node_execution_id, NodeExecutionStatus.SUCCEEDED, self._clock.now())
        self._emit_node_event(
            cursor,
            "node.finished",
            NodeFinishedPayload(
                node_id=node.id,
                iteration=iteration,
                status=NodeExecutionStatus.SUCCEEDED.value,
            ).model_dump(),
            node.id,
        )
        return None

    def _judge(self, declaration: WorkflowRunDeclaration, node: Node) -> bool:
        """`CONDITION`·`LOOP` 의 판정 하나(판정할 수 없으면 `ConditionFailure`). **`LOOP` 만** 예외
        하나를 가집니다(spec 0005 2.7 개정 8 (1)): 판정식이 이 Version 의 노드 출력을 가리키는데 그
        노드의 기록이 아직 없으면 "계속"(참)입니다 - 본문 출력으로 탈출하는 조건 루프의 첫 판정이
        `condition_path_missing` 으로 죽지 않게. 그래프에 없는 노드(오타)는 이 예외가 아닙니다."""
        if node.condition_path is None or node.condition_operator is None:
            raise ConditionFailure(WorkflowFailureReason.INVALID_GRAPH)
        if node.kind is NodeKind.LOOP and points_at_unrecorded_node(
            node.condition_path,
            (n.id for n in declaration.nodes),
            (r.node_id for r in self._store.node_executions(declaration.workflow_run_id)),
        ):
            return True
        return evaluate_condition(
            self._condition_context(declaration),
            node.condition_path,
            node.condition_operator,
            node.condition_value,
        )

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

    # -- JOIN -----------------------------------------------------------------

    def _run_join_node(
        self,
        cursor: _Cursor,
        node: Node,
        declaration: WorkflowRunDeclaration,
        progress: Progress,
        iteration: int,
    ) -> WorkflowRunStatus | None:
        """모든 분기가 결판난 뒤에 전진합니다(`Progress` 가 보장). 출력은 분기별 결과이고 분기
        하나라도
        실패했으면 `failed` + `branch_failed` 로 기록하고 Workflow 를 끝냅니다(R-9). 분기의 출력은
        `_condition_context` 에서만 읽습니다 - 출력을 읽는 곳은 하나입니다(C-3)."""
        run_id = cursor.workflow_run_id
        node_execution_id = self._store.start_node(run_id, node.id, iteration)
        if node_execution_id is not None:
            self._emit_node_event(
                cursor,
                "node.started",
                NodeStartedPayload(
                    node_id=node.id, kind=node.kind.value, iteration=iteration
                ).model_dump(),
                node.id,
            )
        else:
            record = self._record(run_id, node.id, iteration)
            if record is None:
                raise RuntimeError(f"node {node.id} of {run_id} is recorded but not readable")
            node_execution_id = record.id

        outputs = self._condition_context(declaration)["nodes"]
        branches = {source: outputs.get(source) for source in progress.incoming_sources(node.id)}
        merged = join_output(branches, self._output_max_bytes)
        failed = progress.has_blocked_input(node.id)
        status = NodeExecutionStatus.FAILED if failed else NodeExecutionStatus.SUCCEEDED
        reason = WorkflowFailureReason.BRANCH_FAILED if failed else None
        self._store.finish_node(node_execution_id, status, self._clock.now(), reason, merged)
        self._emit_node_event(
            cursor,
            "node.finished",
            NodeFinishedPayload(
                node_id=node.id, iteration=iteration, status=status.value
            ).model_dump(),
            node.id,
        )
        if reason is None:
            return None
        return self._finish(cursor, WorkflowRunStatus.FAILED, reason, node_id=node.id)

    # -- WAIT 노드와 타이머 대기 ------------------------------------------------------

    def _timer_elapsed(self, wake_at: datetime | None) -> bool:
        """`wake_at` 이 지났는가. **대기가 끝났는지를 정하는 곳은 여기 하나**입니다. 시각을 모르면
        (`None`) 더 기다릴 근거가 없으므로 끝난 것으로 보고, 노드 쪽 재개가 다시 파킹하며
        정합니다."""
        return wake_at is None or self._clock.now() >= wake_at

    def _run_wait_node(
        self, cursor: _Cursor, node: Node, iteration: int
    ) -> WorkflowRunStatus | None:
        """`None` 이면 대기가 끝나 노드를 마쳤으니 다음으로 갑니다. 아니면 이 호출이 끝나는 상태
        (`waiting_timer` 파킹 또는 실패 종결)입니다.

        `start_node` 가 `None`(이미 기록됨)이고 그 행이 `waiting_timer` 이며 파킹 때 저장한
        `wake_at` 이 지났을 때만 마칩니다(R-6, R-8). 그 밖의 재개 - 행만 만들고 죽음(`running`),
        노드만 파킹하고 Run 상태를 저장하기 전에 죽음(`wake_at` 을 모름) - 는 새 행 없이 다시
        파킹하며 `wake_at` 을 정합니다(기다림이 늘어날 뿐 앞서지는 않습니다)."""
        run_id = cursor.workflow_run_id
        node_execution_id = self._store.start_node(run_id, node.id, iteration)
        if node_execution_id is not None:
            self._emit_node_event(
                cursor,
                "node.started",
                NodeStartedPayload(
                    node_id=node.id, kind=node.kind.value, iteration=iteration
                ).model_dump(),
                node.id,
            )
        else:
            record = self._record(run_id, node.id, iteration)
            if record is None:
                raise RuntimeError(f"node {node.id} of {run_id} is recorded but not readable")
            node_execution_id = record.id
            if record.status not in (
                NodeExecutionStatus.RUNNING,
                NodeExecutionStatus.WAITING_TIMER,
            ):
                return None
            if (
                record.status is NodeExecutionStatus.WAITING_TIMER
                and cursor.wake_at is not None
                and self._timer_elapsed(cursor.wake_at)
            ):
                self._store.finish_node(
                    node_execution_id, NodeExecutionStatus.SUCCEEDED, self._clock.now()
                )
                self._emit_node_event(
                    cursor,
                    "node.finished",
                    NodeFinishedPayload(
                        node_id=node.id,
                        iteration=iteration,
                        status=NodeExecutionStatus.SUCCEEDED.value,
                    ).model_dump(),
                    node.id,
                )
                return None

        wake_at = cursor.wake_at
        if wake_at is None:
            if node.wait_seconds is None or node.wait_seconds <= 0:
                # 저장 때 걸러지는 모양(`wait_node_without_duration`) - 얼마나 기다릴지 모르는 채
                # 파킹하면 Run 이 영원히 멈춘다.
                return self._fail_node(
                    cursor, node, node_execution_id, WorkflowFailureReason.INVALID_GRAPH, iteration
                )
            wake_at = self._clock.now() + timedelta(seconds=node.wait_seconds)
        return self._park_for_timer(cursor, node, node_execution_id, wake_at)

    def _park_for_timer(
        self, cursor: _Cursor, node: Node, node_execution_id: UUID, wake_at: datetime
    ) -> WorkflowRunStatus:
        """`waiting_timer` 로 내려갑니다: 노드를 대기로 표시하고, Run 상태와 `wake_at` 을 저장하고,
        **lease 를 놓고**, `workflow.status` 를 발행·통지합니다(순서의 이유는
        `_release_before_announcing`). 새 이벤트 타입은 없습니다."""
        if not can_transition(WorkflowRunStatus.RUNNING, WorkflowRunStatus.WAITING_TIMER):
            raise IllegalWorkflowTransition(
                WorkflowRunStatus.RUNNING, WorkflowRunStatus.WAITING_TIMER
            )
        self._store.park_node_for_timer(node_execution_id)
        now = self._clock.now()
        cursor.seq += 1
        cursor.node_id = node.id
        self._store.set_status(
            cursor.workflow_run_id,
            WorkflowRunStatus.WAITING_TIMER,
            seq=cursor.seq,
            current_node_id=node.id,
            wake_at=wake_at,
        )
        self._release_before_announcing(cursor)
        self._publish(
            cursor,
            "workflow.status",
            WorkflowStatusPayload(
                status=WorkflowRunStatus.WAITING_TIMER.value, current_node_id=node.id
            ).model_dump(exclude_none=True),
            now,
        )
        self._notifier.notify(
            WorkflowStatusMessage(
                workflow_run_id=cursor.workflow_run_id,
                seq=cursor.seq,
                status=WorkflowRunStatus.WAITING_TIMER,
                at=now,
                current_node_id=node.id,
                wake_at=wake_at,
            )
        )
        return WorkflowRunStatus.WAITING_TIMER

    # -- HUMAN / APPROVAL 노드와 승인 대기 -----------------------------------------

    def _approval_is_stored(self, execution: WorkflowRunExecution) -> bool:
        """`waiting_approval` 인 Workflow Run 이 기다리는 노드 실행에 **저장된 승인** 이 있는가.
        기다리는 노드 실행을 알 수 없으면(포인터 없음) 승인을 증명할 수 없으므로 `False` - 멈춘 채로
        둡니다(fail-closed). 이 판정에 재큐 메시지는 관여하지 않습니다."""
        awaited = execution.waiting_node_execution_id
        if awaited is None:
            return False
        return self._approvals.approval_for(awaited) is not None

    def _run_approval_node(
        self, cursor: _Cursor, node: Node, iteration: int
    ) -> WorkflowRunStatus | None:
        """`HUMAN` 과 `APPROVAL` 은 v1 에서 **같다**(spec 2.6 개정 5 (5)). `None` 이면 승인이 저장돼
        노드를 마쳤으니 다음으로 갑니다. 아니면 이 호출이 끝나는 상태(`waiting_approval`
        파킹)입니다.

        여기에 "누가 승인했는가" 를 묻는 코드는 없습니다 - 권한 모델은 만들지 않습니다(C-4)."""
        run_id = cursor.workflow_run_id
        node_execution_id = self._store.start_node(run_id, node.id, iteration)
        if node_execution_id is not None:
            self._emit_node_event(
                cursor,
                "node.started",
                NodeStartedPayload(
                    node_id=node.id, kind=node.kind.value, iteration=iteration
                ).model_dump(),
                node.id,
            )
            return self._park_for_approval(cursor, node, node_execution_id, iteration)

        # 이미 기록돼 있다 - 새 실행이 아니라 재개입니다(R-6, R-8).
        record = self._record(run_id, node.id, iteration)
        if record is None:
            raise RuntimeError(f"node {node.id} of {run_id} is recorded but not readable")
        # `running`(시작만 하고 죽음) 또는 `waiting_approval`: 저장된 승인이 있어야만 마친다. 상태
        # 쪽 검사(`_approval_is_stored`)를 지난 뒤에도 노드 쪽에서 한 번 더 묻는 이유는, 상태를
        # 저장하기 전에 죽은 재전달도 같은 규칙으로 판정하기 위해서다.
        if self._approvals.approval_for(record.id) is None:
            return self._park_for_approval(cursor, node, record.id, iteration)

        self._store.finish_node(record.id, NodeExecutionStatus.SUCCEEDED, self._clock.now())
        self._emit_node_event(
            cursor,
            "approval.granted",
            ApprovalGrantedPayload(node_id=node.id, iteration=iteration).model_dump(),
            node.id,
        )
        self._emit_node_event(
            cursor,
            "node.finished",
            NodeFinishedPayload(
                node_id=node.id,
                iteration=iteration,
                status=NodeExecutionStatus.SUCCEEDED.value,
            ).model_dump(),
            node.id,
        )
        return None

    def _park_for_approval(
        self, cursor: _Cursor, node: Node, node_execution_id: UUID, iteration: int
    ) -> WorkflowRunStatus:
        """`waiting_approval` 으로 내려갑니다: 노드를 대기로 표시하고, Workflow Run 상태와 기다리는
        노드 실행의 id 를 저장하고, **lease 를 놓고**, 발행·통지하고, `approval.requested` 를 냅니다
        (순서의 이유는 `_release_before_announcing`).

        상태 저장 둘(`workflow.status` 의 `seq` 와 `approval.requested` 의 `seq`)을 **모두** lease
        해제 앞에 둡니다 - 해제 뒤에는 다른 worker 가 이어받아 상태를 바꿀 수 있어서, 그 뒤의
        `set_status` 가 새 상태를 대기로 되돌릴 수 있기 때문입니다."""
        if not can_transition(WorkflowRunStatus.RUNNING, WorkflowRunStatus.WAITING_APPROVAL):
            raise IllegalWorkflowTransition(
                WorkflowRunStatus.RUNNING, WorkflowRunStatus.WAITING_APPROVAL
            )
        self._store.park_node_for_approval(node_execution_id)
        now = self._clock.now()
        cursor.seq += 1
        cursor.node_id = node.id
        status_seq = cursor.seq
        self._store.set_status(
            cursor.workflow_run_id,
            WorkflowRunStatus.WAITING_APPROVAL,
            seq=status_seq,
            current_node_id=node.id,
            waiting_node_execution_id=node_execution_id,
        )
        # 이 `seq` 는 상태 통지가 없는 이벤트의 것이라 투영은 건너뛰고 이벤트 스트림만 앞선다 -
        # 빈틈은 단조성을 해치지 않는다.
        requested_seq = status_seq + 1
        self._store.set_status(
            cursor.workflow_run_id,
            WorkflowRunStatus.WAITING_APPROVAL,
            seq=requested_seq,
            current_node_id=node.id,
        )
        self._release_before_announcing(cursor)
        cursor.seq = status_seq
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
                seq=status_seq,
                status=WorkflowRunStatus.WAITING_APPROVAL,
                at=now,
                current_node_id=node.id,
                waiting_node_execution_id=node_execution_id,
            )
        )
        cursor.seq = requested_seq
        self._publish(
            cursor,
            "approval.requested",
            ApprovalRequestedPayload(node_id=node.id, iteration=iteration).model_dump(),
            now,
        )
        return WorkflowRunStatus.WAITING_APPROVAL

    # -- LLM / TOOL / MCP 노드 ---------------------------------------------------------

    def _run_invoke_node(
        self, cursor: _Cursor, node: Node, declaration: WorkflowRunDeclaration, iteration: int
    ) -> WorkflowRunStatus | None:
        """`None` 이면 노드를 마쳤으니 다음으로 갑니다(파킹이 없습니다). 아니면 실패로 끝난 상태.

        이미 기록된 노드는 `running`(시작만 하고 죽음)일 때만 다시 부르고, 마쳤으면 건너뜁니다."""
        run_id = cursor.workflow_run_id
        node_execution_id = self._store.start_node(run_id, node.id, iteration)
        if node_execution_id is not None:
            self._emit_node_event(
                cursor,
                "node.started",
                NodeStartedPayload(
                    node_id=node.id, kind=node.kind.value, iteration=iteration
                ).model_dump(),
                node.id,
            )
        else:
            record = self._record(run_id, node.id, iteration)
            if record is None:
                raise RuntimeError(f"node {node.id} of {run_id} is recorded but not readable")
            if record.status is not NodeExecutionStatus.RUNNING:
                return None
            node_execution_id = record.id

        outcome = self._invoke(cursor, node, declaration)
        if isinstance(outcome, WorkflowFailureReason):
            return self._fail_node(cursor, node, node_execution_id, outcome, iteration)
        output, failure = outcome
        status = (
            NodeExecutionStatus.FAILED if failure is not None else NodeExecutionStatus.SUCCEEDED
        )
        self._store.finish_node(node_execution_id, status, self._clock.now(), failure, output)
        self._emit_node_event(
            cursor,
            "node.finished",
            NodeFinishedPayload(
                node_id=node.id, iteration=iteration, status=status.value
            ).model_dump(),
            node.id,
        )
        if failure is None:
            return None
        return self._end_in_failure(cursor, node, failure)

    def _invoke(
        self, cursor: _Cursor, node: Node, declaration: WorkflowRunDeclaration
    ) -> tuple[NodeOutput, WorkflowFailureReason | None] | WorkflowFailureReason:
        """모델 또는 도구를 한 번 부릅니다. 부르기 전에 실패하거나 호출이 예외를 내면 사유만,
        호출이 결과를 돌려주면 출력과(도구가 `is_error` 면) 실패 사유를 함께 돌려줍니다 - 실패한
        도구 호출의 결과도 기록에 남기기 위해서입니다."""
        context = self._condition_context(declaration)
        try:
            if node.kind is NodeKind.LLM:
                return self._call_model(node, context)
            return self._call_tool(cursor, node, context)
        except ConditionFailure as failure:
            return failure.reason

    def _call_model(
        self, node: Node, context: dict[str, Any]
    ) -> tuple[NodeOutput, WorkflowFailureReason | None] | WorkflowFailureReason:
        if self._models is None:  # _supported_kinds 가 이미 걸렀다 - 타입 좁히기
            raise RuntimeError("LLM node without a model invoker")
        prompt = build_prompt(node.llm_prompt, node.llm_prompt_path, context)
        try:
            answer = self._models.invoke(prompt, None)
        except Exception:  # noqa: BLE001 - 어떤 모델 실패든 노드 실패이고, 내용은 사유에 담지 않는다
            return WorkflowFailureReason.MODEL_CALL_FAILED
        return llm_output(answer.text, answer.finish_reason, self._output_max_bytes), None

    def _call_tool(
        self, cursor: _Cursor, node: Node, context: dict[str, Any]
    ) -> tuple[NodeOutput, WorkflowFailureReason | None] | WorkflowFailureReason:
        if self._tools is None:  # _supported_kinds 가 이미 걸렀다 - 타입 좁히기
            raise RuntimeError("tool node without a tool invoker")
        if node.agent_id is None or node.tool_server is None or node.tool_name is None:
            return WorkflowFailureReason.AGENT_VERSION_NOT_FOUND
        ref = self._agent_runs.version_for(node.agent_id, node.agent_version)
        if ref is None:
            return WorkflowFailureReason.AGENT_VERSION_NOT_FOUND
        arguments = build_arguments(node.tool_arguments, node.tool_arguments_path, context)
        try:
            result = self._tools.call(
                cursor.workflow_run_id,
                ref.agent_version_id,
                node.tool_server,
                node.tool_name,
                arguments,
            )
        except ToolInvocationDenied:
            return WorkflowFailureReason.TOOL_CALL_DENIED
        except Exception:  # noqa: BLE001 - 호출 실패는 종류와 상관없이 노드 실패
            return WorkflowFailureReason.TOOL_CALL_FAILED
        output = tool_output(result.content, result.is_error, self._output_max_bytes)
        return output, (WorkflowFailureReason.TOOL_CALL_FAILED if result.is_error else None)

    # -- AGENT 노드와 파킹 -----------------------------------------------------

    def _record(self, run_id: UUID, node_id: str, iteration: int) -> NodeExecutionRecord | None:
        return next(
            (
                r
                for r in self._store.node_executions(run_id)
                if r.node_id == node_id and r.iteration == iteration
            ),
            None,
        )

    def _latest_record(self, run_id: UUID, node_id: str) -> NodeExecutionRecord | None:
        """노드의 가장 늦은 회차 기록 - 루프 안의 파킹은 0 회차가 아닐 수 있다."""
        recorded = [r for r in self._store.node_executions(run_id) if r.node_id == node_id]
        return max(recorded, key=lambda r: r.iteration, default=None)

    def _still_waiting(self, execution: WorkflowRunExecution) -> bool:
        """파킹 중인 Workflow 의 자식 Run 이 아직 종결이 아니면 `True`. 자식의 실행 행이 없는 것
        (`None`, 아직 worker 가 집지 않음)도 종결이 아닙니다. 기록이 어긋나 판단할 수 없으면
        `False` 로 두어 전진 경로가 기록을 보고 판정하게 합니다."""
        if execution.current_node_id is None:
            return False
        record = self._latest_record(execution.workflow_run_id, execution.current_node_id)
        if (
            record is None
            or record.status is not NodeExecutionStatus.WAITING_RUN
            or record.agent_run_id is None
        ):
            return False
        child = self._agent_runs.status(record.agent_run_id)
        return child is None or not is_terminal(child)

    def _run_agent_node(
        self, cursor: _Cursor, node: Node, declaration: WorkflowRunDeclaration, iteration: int
    ) -> WorkflowRunStatus | None:
        """`None` 이면 노드를 마쳤으니 다음으로 갑니다. 아니면 이 호출이 끝나는 상태(`waiting_run`
        파킹 또는 종결)입니다."""
        run_id = cursor.workflow_run_id
        node_execution_id = self._store.start_node(run_id, node.id, iteration)
        agent_run_id: UUID | None = None
        if node_execution_id is not None:
            self._emit_node_event(
                cursor,
                "node.started",
                NodeStartedPayload(
                    node_id=node.id, kind=node.kind.value, iteration=iteration
                ).model_dump(),
                node.id,
            )
        else:
            # 이미 기록돼 있다 - 새 실행이 아니라 재개입니다(R-6, R-8).
            record = self._record(run_id, node.id, iteration)
            if record is None:
                raise RuntimeError(f"node {node.id} of {run_id} is recorded but not readable")
            node_execution_id = record.id
            agent_run_id = record.agent_run_id

        if agent_run_id is None:
            # 새 실행(또는 id 를 영속하기 전에 죽은 재개): 해석 -> **영속** -> 발사 -> 파킹.
            resolved = self._resolve(declaration, node)
            if isinstance(resolved, WorkflowFailureReason):
                return self._fail_node(cursor, node, node_execution_id, resolved, iteration)
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
                    return self._fail_node(cursor, node, node_execution_id, resolved, iteration)
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
                node_id=node.id, iteration=iteration, status=node_status.value
            ).model_dump(),
            node.id,
        )
        if succeeded:
            return None
        return self._end_in_failure(cursor, node, WorkflowFailureReason.AGENT_RUN_FAILED)

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
        """`waiting_run` 으로 내려갑니다: 저장하고, **lease 를 놓고**, 발행하고, 통지합니다(순서의
        이유는 `_release_before_announcing`)."""
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
        self._release_before_announcing(cursor)
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
        iteration: int,
    ) -> WorkflowRunStatus | None:
        self._store.finish_node(
            node_execution_id, NodeExecutionStatus.FAILED, self._clock.now(), reason
        )
        self._emit_node_event(
            cursor,
            "node.finished",
            NodeFinishedPayload(
                node_id=node.id,
                iteration=iteration,
                status=NodeExecutionStatus.FAILED.value,
            ).model_dump(),
            node.id,
        )
        return self._end_in_failure(cursor, node, reason)

    def _end_in_failure(
        self, cursor: _Cursor, node: Node, reason: WorkflowFailureReason
    ) -> WorkflowRunStatus | None:
        """노드가 `failed` 로 기록된 뒤의 Workflow 의 운명. `PARALLEL` 분기 안의 노드면 `None` -
        다른 분기를 마저 돌리고 `JOIN` 이 관측합니다(R-9). 그 밖에는 그 사유로 즉시 끝납니다.
        `loop_limit_exceeded` 는 분기 안에서도 감싸지 않습니다 - 구별되는 사유가 `branch_failed` 에
        덮이면 R-10 이 사라집니다."""
        if node.id in cursor.contained and reason is not WorkflowFailureReason.LOOP_LIMIT_EXCEEDED:
            return None
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
