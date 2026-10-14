"""spec 0005 2.3, R-13 (P4-2a A1): `GetWorkflowRunUseCase` — 투영만 읽고, 없으면
`WorkflowRunNotFound`. `waiting_run` 값과 `waiting_run_id` 가 조회에 나타납니다(R-13 의 절반)."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from aether_api.application.ports.inbound.workflows import DefineWorkflowRequest
from aether_api.application.usecases.define_workflow import DefineWorkflowUseCase
from aether_api.application.usecases.get_workflow_run import GetWorkflowRunUseCase
from aether_api.domain.workflow_run import WorkflowRunNotFound, WorkflowRunView
from aether_workflow.domain.node import Edge, Node, NodeKind
from aether_workflow.domain.run_status import WorkflowRunStatus

from apps.api.tests.fakes_workflow import FakeWorkflowRepository, FakeWorkflowRunDeclarationStore


def _declared() -> tuple[FakeWorkflowRunDeclarationStore, WorkflowRunView]:
    repo = FakeWorkflowRepository()
    wf = DefineWorkflowUseCase(repo)(
        DefineWorkflowRequest(
            "wf", (Node("s", NodeKind.START), Node("e", NodeKind.END)), (Edge("s", "e"),)
        )
    )
    store = FakeWorkflowRunDeclarationStore(repo)
    return store, store.create(wf.id, 1, None)


def test_returns_the_declared_view() -> None:
    store, created = _declared()

    assert GetWorkflowRunUseCase(store)(created.workflow_run_id) == created


def test_unknown_id_raises_workflow_run_not_found() -> None:
    store, _ = _declared()

    with pytest.raises(WorkflowRunNotFound):
        GetWorkflowRunUseCase(store)(uuid4())


def test_waiting_run_status_and_target_show_up_in_the_view() -> None:
    """spec 0005 R-13: 투영된 `waiting_run` 과 기다리는 자식 Run id 가 조회에 나타난다."""
    store, created = _declared()
    child = uuid4()
    store.apply_status(
        created.workflow_run_id,
        seq=3,
        status=WorkflowRunStatus.WAITING_RUN,
        current_node_id="a",
        waiting_run_id=child,
        started_at=datetime(2026, 1, 1, tzinfo=UTC),
        finished_at=None,
        failure_reason=None,
    )

    view = GetWorkflowRunUseCase(store)(created.workflow_run_id)

    assert view.status == WorkflowRunStatus.WAITING_RUN
    assert view.waiting_run_id == child
    assert view.current_node_id == "a"
