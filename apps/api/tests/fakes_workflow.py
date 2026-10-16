"""spec 0005 2.9, D-12: `WorkflowRepository` 포트의 인메모리 fake — 컨테이너 없이 Workflow
정의 유스케이스와 라우터를 돕니다(`fakes_knowledge.py` 와 같은 패턴). 테스트 지원 코드이며
제품 코드가 아닙니다.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from aether_api.domain.workflow import WorkflowNotFound, WorkflowVersionNotFound, WorkflowView
from aether_api.domain.workflow_approval import AlreadyApproved, WorkflowApprovalView
from aether_api.domain.workflow_run import WorkflowRunView
from aether_workflow.domain.node import Edge, Node
from aether_workflow.domain.run_status import WorkflowRunStatus
from aether_workflow.domain.workflow_version import WorkflowVersion


class FakeWorkflowRepository:
    """`WorkflowRepository` 포트 계약의 인메모리 구현."""

    def __init__(self) -> None:
        self._names: dict[UUID, str] = {}
        self._versions: dict[UUID, list[WorkflowVersion]] = {}

    def create(self, name: str, nodes: tuple[Node, ...], edges: tuple[Edge, ...]) -> WorkflowView:
        workflow_id = uuid4()
        version = WorkflowVersion(number=1, nodes=nodes, edges=edges)
        self._names[workflow_id] = name
        self._versions[workflow_id] = [version]
        return WorkflowView(id=workflow_id, name=name, latest_version=version)

    def add_version(
        self, workflow_id: UUID, nodes: tuple[Node, ...], edges: tuple[Edge, ...]
    ) -> WorkflowView:
        if workflow_id not in self._versions:
            raise WorkflowNotFound(workflow_id)
        version = WorkflowVersion(
            number=len(self._versions[workflow_id]) + 1, nodes=nodes, edges=edges
        )
        self._versions[workflow_id].append(version)
        return WorkflowView(id=workflow_id, name=self._names[workflow_id], latest_version=version)

    def get(self, workflow_id: UUID) -> WorkflowView | None:
        versions = self._versions.get(workflow_id)
        if versions is None:
            return None
        return WorkflowView(
            id=workflow_id, name=self._names[workflow_id], latest_version=versions[-1]
        )

    def get_version(self, workflow_id: UUID, number: int) -> WorkflowVersion | None:
        versions = self._versions.get(workflow_id, [])
        for version in versions:
            if version.number == number:
                return version
        return None


class FakeWorkflowRunDeclarationStore:
    """`WorkflowRunDeclarationStore` 포트 계약의 인메모리 구현(spec 0005 2.3, 2.9 개정 2).

    `status_seq` 는 `WorkflowRunView` 밖의 내부 부기입니다 — `apply_status` 의 멱등 규칙을
    재현하려면 마지막으로 적용한 `seq` 를 기억해야 합니다. Version 의 존재는
    `FakeWorkflowRepository` 로 판정합니다.
    """

    def __init__(self, repository: FakeWorkflowRepository) -> None:
        self._repository = repository
        self._runs: dict[UUID, WorkflowRunView] = {}
        self._status_seq: dict[UUID, int] = {}
        self._version_ids: dict[tuple[UUID, int], UUID] = {}
        self.inputs: dict[UUID, dict[str, Any] | None] = {}
        self.requesters: dict[UUID, UUID] = {}

    def create(
        self,
        workflow_id: UUID,
        workflow_version: int,
        input: dict[str, Any] | None,
        requested_by: UUID,
    ) -> WorkflowRunView:
        if self._repository.get_version(workflow_id, workflow_version) is None:
            raise WorkflowVersionNotFound(workflow_id, workflow_version)
        version_id = self._version_ids.setdefault((workflow_id, workflow_version), uuid4())
        run_id = uuid4()
        view = WorkflowRunView(
            workflow_run_id=run_id,
            workflow_id=workflow_id,
            workflow_version=workflow_version,
            workflow_version_id=version_id,
            status=WorkflowRunStatus.QUEUED,
            current_node_id=None,
            waiting_run_id=None,
            waiting_node_execution_id=None,
            requested_at=datetime(2026, 1, 1, tzinfo=UTC),
            started_at=None,
            finished_at=None,
            failure_reason=None,
        )
        self._runs[run_id] = view
        self._status_seq[run_id] = 0
        self.inputs[run_id] = input
        self.requesters[run_id] = requested_by
        return view

    def get(self, workflow_run_id: UUID) -> WorkflowRunView | None:
        return self._runs.get(workflow_run_id)

    def apply_status(
        self,
        workflow_run_id: UUID,
        *,
        seq: int,
        status: WorkflowRunStatus,
        current_node_id: str | None,
        waiting_run_id: UUID | None,
        started_at: datetime | None,
        finished_at: datetime | None,
        failure_reason: str | None,
        waiting_node_execution_id: UUID | None = None,
    ) -> bool:
        view = self._runs.get(workflow_run_id)
        if view is None or self._status_seq[workflow_run_id] >= seq:
            return False
        self._status_seq[workflow_run_id] = seq
        self._runs[workflow_run_id] = replace(
            view,
            status=status,
            current_node_id=current_node_id
            if current_node_id is not None
            else view.current_node_id,
            waiting_run_id=_derived(
                status is WorkflowRunStatus.WAITING_RUN, waiting_run_id, view.waiting_run_id
            ),
            waiting_node_execution_id=_derived(
                status is WorkflowRunStatus.WAITING_APPROVAL,
                waiting_node_execution_id,
                view.waiting_node_execution_id,
            ),
            started_at=started_at if started_at is not None else view.started_at,
            finished_at=finished_at if finished_at is not None else view.finished_at,
            failure_reason=failure_reason if failure_reason is not None else view.failure_reason,
        )
        return True


def _derived(waiting: bool, new: UUID | None, old: UUID | None) -> UUID | None:
    """상태에서 유도되는 포인터(`waiting_run_id`·`waiting_node_execution_id`): 그 대기 상태일 때만
    값이 있고(주지 않으면 이전 값) 다른 상태로 가면 지워진다 - PostgreSQL 구현의 `CASE` 와 같다."""
    if not waiting:
        return None
    return new if new is not None else old


class FakeWorkflowApprovalStore:
    """`WorkflowApprovalStore` 포트 계약의 인메모리 구현. 노드 실행당 한 건 - 두 번째 `record` 는
    `AlreadyApproved`(PostgreSQL 의 `unique(workflow_run_id, node_execution_id)` 와 같다)."""

    def __init__(self) -> None:
        self.approvals: list[WorkflowApprovalView] = []

    def record(
        self, workflow_run_id: UUID, node_execution_id: UUID, approved_by: str, note: str | None
    ) -> WorkflowApprovalView:
        if self.get(workflow_run_id, node_execution_id) is not None:
            raise AlreadyApproved(workflow_run_id, node_execution_id)
        view = WorkflowApprovalView(
            workflow_run_id=workflow_run_id,
            node_execution_id=node_execution_id,
            approved_by=approved_by,
            approved_at=datetime(2026, 1, 1, 0, len(self.approvals), tzinfo=UTC),
            note=note,
        )
        self.approvals.append(view)
        return view

    def get(self, workflow_run_id: UUID, node_execution_id: UUID) -> WorkflowApprovalView | None:
        return next(
            (
                a
                for a in self.approvals
                if a.workflow_run_id == workflow_run_id and a.node_execution_id == node_execution_id
            ),
            None,
        )

    def list_for(self, workflow_run_id: UUID) -> tuple[WorkflowApprovalView, ...]:
        return tuple(a for a in self.approvals if a.workflow_run_id == workflow_run_id)


class FakeWorkflowRunNotifier:
    """`WorkflowRunNotifier` 포트의 인메모리 구현. `should_fail` 이면 `requested` 가 예외를
    던집니다 — `StartWorkflowRunUseCase` 가 삼키고 WARNING 을 남기는지 테스트가 증명합니다."""

    def __init__(self, *, should_fail: bool = False) -> None:
        self.calls: list[tuple[UUID, UUID, str | None]] = []
        self._should_fail = should_fail

    def requested(
        self, workflow_run_id: UUID, workflow_version_id: UUID, traceparent: str | None
    ) -> None:
        self.calls.append((workflow_run_id, workflow_version_id, traceparent))
        if self._should_fail:
            raise RuntimeError("FakeWorkflowRunNotifier: injected requested failure")
