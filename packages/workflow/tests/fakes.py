"""spec 0005 2.9 개정 2: `aether_workflow` 의 outbound 포트 인메모리 fake — 컨테이너 없이
`AdvanceWorkflowRunUseCase` 를 돕니다. 테스트 지원 코드이며 제품 코드가 아닙니다.

이름은 `FakeWorkflow*` 로 `packages/runtime/tests/fakes.py` 의 `FakeClock`·`FakeEventSink`·
`FakeStatusNotifier` 와 겹치지 않게 지었습니다(`tests/arch/test_fake_duplication.py`).
"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from aether_workflow.application.ports.outbound.workflow_run_declaration_reader import (
    WorkflowRunDeclaration,
)
from aether_workflow.application.ports.outbound.workflow_status_notifier import (
    WorkflowStatusMessage,
)
from aether_workflow.domain.events import WorkflowEvent
from aether_workflow.domain.failure import WorkflowFailureReason
from aether_workflow.domain.node import Edge, Node, NodeKind
from aether_workflow.domain.node_execution import NodeExecutionRecord, NodeExecutionStatus
from aether_workflow.domain.run_execution import WorkflowRunExecution
from aether_workflow.domain.run_status import WorkflowRunStatus

_EPOCH = datetime(2026, 10, 14, tzinfo=UTC)


class FakeWorkflowClock:
    """호출마다 1 초씩 앞서는 결정적 시계."""

    def __init__(self) -> None:
        self._now = _EPOCH

    def now(self) -> datetime:
        self._now += timedelta(seconds=1)
        return self._now


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
        self, workflow_run_id: UUID, node_id: str, status: NodeExecutionStatus
    ) -> NodeExecutionRecord:
        record = NodeExecutionRecord(
            id=uuid4(),
            workflow_run_id=workflow_run_id,
            node_id=node_id,
            iteration=0,
            status=status,
            started_at=_EPOCH,
            finished_at=None if status is NodeExecutionStatus.RUNNING else _EPOCH,
        )
        self.nodes.setdefault(workflow_run_id, []).append(record)
        return record

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
    ) -> None:
        self.set_status_calls.append((status, seq))
        old = self.executions[workflow_run_id]
        self.executions[workflow_run_id] = replace(
            old,
            status=status,
            status_seq=seq,
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

    def finish_node(
        self, node_execution_id: UUID, status: NodeExecutionStatus, finished_at: datetime
    ) -> None:
        for records in self.nodes.values():
            for index, record in enumerate(records):
                if record.id == node_execution_id:
                    records[index] = replace(record, status=status, finished_at=finished_at)
                    return
        raise KeyError(node_execution_id)

    def node_executions(self, workflow_run_id: UUID) -> tuple[NodeExecutionRecord, ...]:
        return tuple(self.nodes.get(workflow_run_id, []))


class FakeWorkflowRunDeclarationReader:
    def __init__(self) -> None:
        self._declarations: dict[UUID, WorkflowRunDeclaration] = {}

    def add(self, nodes: tuple[Node, ...], edges: tuple[Edge, ...]) -> UUID:
        workflow_run_id = uuid4()
        self._declarations[workflow_run_id] = WorkflowRunDeclaration(
            workflow_run_id=workflow_run_id,
            workflow_version_id=uuid4(),
            version_number=1,
            nodes=nodes,
            edges=edges,
            input=None,
            cancel_requested_at=None,
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


class FakeWorkflowStatusNotifier:
    def __init__(self) -> None:
        self.messages: list[WorkflowStatusMessage] = []

    def notify(self, message: WorkflowStatusMessage) -> None:
        self.messages.append(message)


def start_end_graph() -> tuple[tuple[Node, ...], tuple[Edge, ...]]:
    return (
        (Node("start", NodeKind.START), Node("end", NodeKind.END)),
        (Edge("start", "end"),),
    )
