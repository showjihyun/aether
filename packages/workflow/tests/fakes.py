"""spec 0005 2.9 개정 2: `aether_workflow` 의 outbound 포트 인메모리 fake — 컨테이너 없이
`AdvanceWorkflowRunUseCase` 를 돕니다. 테스트 지원 코드이며 제품 코드가 아닙니다.

이름은 `FakeWorkflow*` 로 `packages/runtime/tests/fakes.py` 의 `FakeClock`·`FakeEventSink`·
`FakeStatusNotifier` 와 겹치지 않게 지었습니다(`tests/arch/test_fake_duplication.py`).
"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

from aether_runtime.domain.run import RunStatus
from aether_workflow.application.ports.outbound.agent_run_launcher import AgentRunLaunch
from aether_workflow.application.ports.outbound.agent_run_reader import AgentVersionRef
from aether_workflow.application.ports.outbound.model_invoker import ModelAnswer
from aether_workflow.application.ports.outbound.tool_invoker import ToolOutcome
from aether_workflow.application.ports.outbound.workflow_node_status_notifier import (
    WorkflowNodeStatusMessage,
)
from aether_workflow.application.ports.outbound.workflow_run_declaration_reader import (
    WorkflowRunDeclaration,
)
from aether_workflow.application.ports.outbound.workflow_status_notifier import (
    WorkflowStatusMessage,
)
from aether_workflow.domain.approval import Approval
from aether_workflow.domain.events import WorkflowEvent
from aether_workflow.domain.failure import WorkflowFailureReason
from aether_workflow.domain.node import Edge, Node, NodeKind
from aether_workflow.domain.node_execution import NodeExecutionRecord, NodeExecutionStatus
from aether_workflow.domain.node_output import NodeOutput
from aether_workflow.domain.run_execution import WorkflowRunExecution
from aether_workflow.domain.run_status import WorkflowRunStatus

_EPOCH = datetime(2026, 10, 14, tzinfo=UTC)

REQUESTER = UUID("00000000-0000-0000-0000-00000000aaaa")
"""선언 fake 의 기본 요청자 - `AGENT` 노드가 `workflow_run_without_requester` 로 막히지 않게."""


class FakeWorkflowClock:
    """호출마다 1 초씩 앞서는 결정적 시계."""

    def __init__(self) -> None:
        self._now = _EPOCH

    def now(self) -> datetime:
        self._now += timedelta(seconds=1)
        return self._now

    def peek(self) -> datetime:
        """시계를 움직이지 않고 지금 값을 본다."""
        return self._now

    def jump(self, seconds: float) -> None:
        """시계를 앞으로 돌린다(R-11) - 실제로 기다리지 않는다."""
        self._now += timedelta(seconds=seconds)


class FakeWorkflowRunStateStore:
    """`WorkflowRunStateStore` 계약의 인메모리 구현. lease 는 시간 없이 "쥔 owner 가 있으면
    실패" 로 단순화합니다(만료 판정은 DB 시계의 몫이라 통합 테스트가 봅니다)."""

    def __init__(self) -> None:
        self.executions: dict[UUID, WorkflowRunExecution] = {}
        self.lease_owner: dict[UUID, str | None] = {}
        self.nodes: dict[UUID, list[NodeExecutionRecord]] = {}
        self.released: list[tuple[UUID, str]] = []
        self.start_node_calls: list[tuple[str, int]] = []
        self.set_status_calls: list[tuple[WorkflowRunStatus, int]] = []
        self.events_log: list[tuple[str, UUID]] = []
        """`park_node`·`launch` 가 일어난 순서 - 영속이 발사보다 먼저인지 판정합니다."""
        self.call_log: list[str] = []
        """`set_status:<상태>`·`release`·`publish:<타입>[:<상태>]`·`notify:<상태>` 가 일어난 순서 -
        파킹이 lease 를 발행·통지보다 먼저 놓는지 판정합니다(spec 0005 2.5 개정 8 (2)). 발행·통지
        쪽은
        `LoggingWorkflowEventSink`·`LoggingWorkflowStatusNotifier` 가 같은 목록에 적습니다."""

    def seed(
        self,
        workflow_run_id: UUID,
        *,
        status: WorkflowRunStatus,
        status_seq: int = 0,
        current_node_id: str | None = None,
    ) -> None:
        self.executions[workflow_run_id] = WorkflowRunExecution(
            workflow_run_id=workflow_run_id,
            status=status,
            status_seq=status_seq,
            current_node_id=current_node_id,
            started_at=None if status is WorkflowRunStatus.QUEUED else _EPOCH,
            finished_at=None,
            failure_reason=None,
        )
        self.lease_owner.setdefault(workflow_run_id, None)

    def seed_node(
        self,
        workflow_run_id: UUID,
        node_id: str,
        status: NodeExecutionStatus,
        *,
        agent_run_id: UUID | None = None,
        iteration: int = 0,
        output: dict[str, Any] | None = None,
    ) -> NodeExecutionRecord:
        record = NodeExecutionRecord(
            agent_run_id=agent_run_id,
            id=uuid4(),
            workflow_run_id=workflow_run_id,
            node_id=node_id,
            iteration=iteration,
            status=status,
            started_at=_EPOCH,
            finished_at=None if status is NodeExecutionStatus.RUNNING else _EPOCH,
            output=output,
        )
        self.nodes.setdefault(workflow_run_id, []).append(record)
        return record

    def replace_output(self, workflow_run_id: UUID, node_id: str, output: dict[str, Any]) -> None:
        """이미 기록된 노드의 출력을 바꿉니다 - 루프 판정의 맥락이 회차 사이에 바뀌는 것을
        흉내냅니다."""
        for index, record in enumerate(self.nodes[workflow_run_id]):
            if record.node_id == node_id:
                self.nodes[workflow_run_id][index] = replace(record, output=output)
                return
        raise KeyError(node_id)

    def hold(self, workflow_run_id: UUID, owner: str) -> None:
        self.lease_owner[workflow_run_id] = owner

    def acquire_lease(self, workflow_run_id: UUID, owner: str, ttl_seconds: float) -> bool:
        if workflow_run_id not in self.executions:
            self.seed(workflow_run_id, status=WorkflowRunStatus.QUEUED)
        if self.lease_owner.get(workflow_run_id) is not None:
            return False
        self.lease_owner[workflow_run_id] = owner
        return True

    def renew_lease(self, workflow_run_id: UUID, owner: str, ttl_seconds: float) -> bool:
        return self.lease_owner.get(workflow_run_id) == owner

    def release(self, workflow_run_id: UUID, owner: str) -> None:
        self.call_log.append("release")
        self.released.append((workflow_run_id, owner))
        if self.lease_owner.get(workflow_run_id) == owner:
            self.lease_owner[workflow_run_id] = None

    def load(self, workflow_run_id: UUID) -> WorkflowRunExecution | None:
        return self.executions.get(workflow_run_id)

    def set_status(
        self,
        workflow_run_id: UUID,
        status: WorkflowRunStatus,
        *,
        seq: int,
        current_node_id: str | None = None,
        failure_reason: WorkflowFailureReason | None = None,
        started_at: datetime | None = None,
        finished_at: datetime | None = None,
        waiting_run_id: UUID | None = None,
        waiting_node_execution_id: UUID | None = None,
        wake_at: datetime | None = None,
    ) -> None:
        self.set_status_calls.append((status, seq))
        self.call_log.append(f"set_status:{status.value}")
        old = self.executions[workflow_run_id]
        if status is WorkflowRunStatus.WAITING_RUN:
            waiting = waiting_run_id if waiting_run_id is not None else old.waiting_run_id
        else:
            waiting = None
        if status is WorkflowRunStatus.WAITING_APPROVAL:
            waiting_node = (
                waiting_node_execution_id
                if waiting_node_execution_id is not None
                else old.waiting_node_execution_id
            )
        else:
            waiting_node = None
        if status is WorkflowRunStatus.WAITING_TIMER:
            wake = wake_at if wake_at is not None else old.wake_at
        else:
            wake = None
        self.executions[workflow_run_id] = replace(
            old,
            status=status,
            status_seq=seq,
            waiting_run_id=waiting,
            waiting_node_execution_id=waiting_node,
            wake_at=wake,
            current_node_id=current_node_id or old.current_node_id,
            failure_reason=failure_reason.value if failure_reason else old.failure_reason,
            started_at=started_at or old.started_at,
            finished_at=finished_at or old.finished_at,
        )

    def start_node(self, workflow_run_id: UUID, node_id: str, iteration: int) -> UUID | None:
        self.start_node_calls.append((node_id, iteration))
        records = self.nodes.setdefault(workflow_run_id, [])
        if any(r.node_id == node_id and r.iteration == iteration for r in records):
            return None
        record = NodeExecutionRecord(
            id=uuid4(),
            workflow_run_id=workflow_run_id,
            node_id=node_id,
            iteration=iteration,
            status=NodeExecutionStatus.RUNNING,
            started_at=_EPOCH,
            finished_at=None,
        )
        records.append(record)
        return record.id

    def park_node(self, node_execution_id: UUID, agent_run_id: UUID) -> None:
        self.events_log.append(("park_node", agent_run_id))
        self._update_node(
            node_execution_id, status=NodeExecutionStatus.WAITING_RUN, agent_run_id=agent_run_id
        )

    def park_node_for_approval(self, node_execution_id: UUID) -> None:
        self.events_log.append(("park_node_for_approval", node_execution_id))
        self._update_node(node_execution_id, status=NodeExecutionStatus.WAITING_APPROVAL)

    def park_node_for_timer(self, node_execution_id: UUID) -> None:
        self.events_log.append(("park_node_for_timer", node_execution_id))
        self._update_node(node_execution_id, status=NodeExecutionStatus.WAITING_TIMER)

    def finish_node(
        self,
        node_execution_id: UUID,
        status: NodeExecutionStatus,
        finished_at: datetime,
        failure_reason: WorkflowFailureReason | None = None,
        output: NodeOutput | None = None,
    ) -> None:
        changes: dict[str, Any] = {
            "status": status,
            "finished_at": finished_at,
            "failure_reason": failure_reason.value if failure_reason is not None else None,
        }
        if output is not None:
            changes["output"] = output.value
            changes["output_truncated"] = output.truncated
        self._update_node(node_execution_id, **changes)

    def _update_node(self, node_execution_id: UUID, **changes: Any) -> None:
        for records in self.nodes.values():
            for index, record in enumerate(records):
                if record.id == node_execution_id:
                    records[index] = replace(record, **changes)
                    return
        raise KeyError(node_execution_id)

    def node_executions(self, workflow_run_id: UUID) -> tuple[NodeExecutionRecord, ...]:
        return tuple(self.nodes.get(workflow_run_id, []))


class FakeWorkflowRunDeclarationReader:
    def __init__(self) -> None:
        self._declarations: dict[UUID, WorkflowRunDeclaration] = {}

    def add(
        self,
        nodes: tuple[Node, ...],
        edges: tuple[Edge, ...],
        *,
        input: dict[str, Any] | None = None,
        requested_by: UUID | None = REQUESTER,
    ) -> UUID:
        workflow_run_id = uuid4()
        self._declarations[workflow_run_id] = WorkflowRunDeclaration(
            workflow_run_id=workflow_run_id,
            workflow_version_id=uuid4(),
            version_number=1,
            nodes=nodes,
            edges=edges,
            input=input,
            cancel_requested_at=None,
            requested_by=requested_by,
        )
        return workflow_run_id

    def declaration(self, workflow_run_id: UUID) -> WorkflowRunDeclaration | None:
        return self._declarations.get(workflow_run_id)


class FakeWorkflowEventSink:
    """발행된 이벤트를 순서대로 모읍니다. `fail_on` 타입을 만나면 예외를 던집니다."""

    def __init__(self, *, fail_on: str | None = None) -> None:
        self.events: list[WorkflowEvent] = []
        self._fail_on = fail_on

    def publish(self, event: WorkflowEvent) -> None:
        if self._fail_on is not None and event.type == self._fail_on:
            raise ConnectionError("sink down")
        self.events.append(event)


class LoggingWorkflowEventSink(FakeWorkflowEventSink):
    """발행이 `store.call_log` 에도 적히는 sink - 저장소 호출과 발행의 **상대 순서**를 봅니다."""

    def __init__(self, log: list[str]) -> None:
        super().__init__()
        self._log = log

    def publish(self, event: WorkflowEvent) -> None:
        status = event.payload.get("status")
        self._log.append(f"publish:{event.type}" + (f":{status}" if status else ""))
        super().publish(event)


class FakeWorkflowStatusNotifier:
    def __init__(self) -> None:
        self.messages: list[WorkflowStatusMessage] = []

    def notify(self, message: WorkflowStatusMessage) -> None:
        self.messages.append(message)


class FakeWorkflowNodeStatusNotifier:
    def __init__(self) -> None:
        self.messages: list[WorkflowNodeStatusMessage] = []

    def notify(self, message: WorkflowNodeStatusMessage) -> None:
        self.messages.append(message)


class FakeApprovalReader:
    """`ApprovalReader` 계약의 인메모리 구현. 승인은 테스트가 `grant` 로 **저장**한 것만 있고,
    `lookups` 는 실행기가 어느 노드 실행의 승인을 물었는지 모읍니다 - 전진의 근거가 저장된
    승인이지 다른 신호가 아님을 판정합니다."""

    def __init__(self) -> None:
        self._granted: dict[UUID, Approval] = {}
        self.lookups: list[UUID] = []

    def grant(self, node_execution_id: UUID) -> None:
        self._granted[node_execution_id] = Approval(
            node_execution_id=node_execution_id, approved_at=_EPOCH
        )

    def approval_for(self, node_execution_id: UUID) -> Approval | None:
        self.lookups.append(node_execution_id)
        return self._granted.get(node_execution_id)


class LoggingWorkflowStatusNotifier(FakeWorkflowStatusNotifier):
    """통지가 `store.call_log` 에도 적히는 notifier."""

    def __init__(self, log: list[str]) -> None:
        super().__init__()
        self._log = log

    def notify(self, message: WorkflowStatusMessage) -> None:
        self._log.append(f"notify:{message.status.value}")
        super().notify(message)


def start_end_graph() -> tuple[tuple[Node, ...], tuple[Edge, ...]]:
    return (
        (Node("start", NodeKind.START), Node("end", NodeKind.END)),
        (Edge("start", "end"),),
    )


class FakeAgentRunReader:
    """`AgentRunReader` 계약의 인메모리 구현. 자식 Run 의 상태는 테스트가 `set_status` 로 정하고,
    정하지 않은 Run 은 `None`(아직 worker 가 집지 않음)입니다."""

    def __init__(self) -> None:
        self.statuses: dict[UUID, RunStatus] = {}
        self.versions: dict[tuple[UUID, int | None], AgentVersionRef] = {}
        self.version_lookups: list[tuple[UUID, int | None]] = []
        self.texts: dict[UUID, str] = {}

    def set_status(self, agent_run_id: UUID, status: RunStatus) -> None:
        self.statuses[agent_run_id] = status

    def set_text(self, agent_run_id: UUID, text: str) -> None:
        """자식 Run 의 마지막 assistant 본문을 정한다. 정하지 않은 Run 은 `None`."""
        self.texts[agent_run_id] = text

    def last_assistant_text(self, agent_run_id: UUID) -> str | None:
        return self.texts.get(agent_run_id)

    def add_version(self, agent_id: UUID, version: int | None) -> AgentVersionRef:
        ref = AgentVersionRef(agent_version_id=uuid4(), version=version or 1)
        self.versions[(agent_id, version)] = ref
        return ref

    def status(self, agent_run_id: UUID) -> RunStatus | None:
        return self.statuses.get(agent_run_id)

    def version_for(self, agent_id: UUID, version: int | None) -> AgentVersionRef | None:
        self.version_lookups.append((agent_id, version))
        return self.versions.get((agent_id, version))


class FakeAgentRunLauncher:
    """발사된 요청을 모읍니다. `store` 를 주면 **발사하는 순간** 노드 실행 기록에 같은
    `agent_run_id` 가 이미 영속돼 있었는지를 `persisted_at_launch` 에 기록합니다 - 영속이 발사보다
    먼저여야 재전달에서 자식 Run 이 둘이 되지 않습니다(R-8)."""

    def __init__(
        self, store: FakeWorkflowRunStateStore | None = None, *, fail_with: Exception | None = None
    ) -> None:
        self.launches: list[AgentRunLaunch] = []
        self.persisted_at_launch: list[bool] = []
        self._store = store
        self._fail_with = fail_with

    def launch(self, request: AgentRunLaunch) -> None:
        if self._store is not None:
            self._store.events_log.append(("launch", request.agent_run_id))
            self.persisted_at_launch.append(
                any(
                    record.agent_run_id == request.agent_run_id
                    for records in self._store.nodes.values()
                    for record in records
                )
            )
        if self._fail_with is not None:
            raise self._fail_with
        self.launches.append(request)


class FakeWorkflowModelInvoker:
    """`ModelInvoker` 계약의 인메모리 구현 - 부른 프롬프트를 모으고 정해 둔 답을 돌려줍니다.
    `fail_with` 를 주면 호출이 그 예외를 냅니다."""

    def __init__(
        self,
        answer: ModelAnswer | None = None,
        *,
        fail_with: Exception | None = None,
    ) -> None:
        self.answer = answer or ModelAnswer(text="echo", finish_reason="stop")
        self.calls: list[tuple[str, str | None]] = []
        self._fail_with = fail_with

    def invoke(self, prompt: str, model_id: str | None) -> ModelAnswer:
        self.calls.append((prompt, model_id))
        if self._fail_with is not None:
            raise self._fail_with
        return self.answer


class FakeWorkflowToolInvoker:
    """`ToolInvoker` 계약의 인메모리 구현 - 부른 것을 모으고 정해 둔 결과를 돌려줍니다.
    `fail_with` 를 주면 호출이 그 예외를 냅니다(거부는 `ToolInvocationDenied`)."""

    def __init__(
        self,
        outcome: ToolOutcome | None = None,
        *,
        fail_with: Exception | None = None,
    ) -> None:
        self.outcome = outcome or ToolOutcome(content="4", is_error=False)
        self.calls: list[tuple[UUID, UUID, str, str, dict[str, Any]]] = []
        self._fail_with = fail_with

    def call(
        self,
        workflow_run_id: UUID,
        agent_version_id: UUID,
        server: str,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> ToolOutcome:
        self.calls.append((workflow_run_id, agent_version_id, server, tool_name, arguments))
        if self._fail_with is not None:
            raise self._fail_with
        return self.outcome
