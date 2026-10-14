"""spec 0005 2.9 개정 2, 2.10 (P4-2a A1): `ApplyWorkflowRunStatusUseCase` — 저장소에
위임만 합니다. `seq` 단조 증가 규칙과 `COALESCE` 는 저장소가 소유합니다(PostgreSQL 쪽은
`test_workflow_run_executions_integration.py` 가 증명합니다)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from aether_api.application.ports.inbound.workflows import DefineWorkflowRequest
from aether_api.application.usecases.apply_workflow_run_status import (
    ApplyWorkflowRunStatusUseCase,
)
from aether_api.application.usecases.define_workflow import DefineWorkflowUseCase
from aether_api.domain.workflow_run import WorkflowRunView
from aether_api.domain.workflow_run_status_message import WorkflowRunStatusMessage
from aether_workflow.domain.node import Edge, Node, NodeKind
from aether_workflow.domain.run_status import WorkflowRunStatus

from apps.api.tests.fakes_workflow import FakeWorkflowRepository, FakeWorkflowRunDeclarationStore


def _store_with_run() -> tuple[FakeWorkflowRunDeclarationStore, UUID]:
    repo = FakeWorkflowRepository()
    wf = DefineWorkflowUseCase(repo)(
        DefineWorkflowRequest(
            "wf", (Node("s", NodeKind.START), Node("e", NodeKind.END)), (Edge("s", "e"),)
        )
    )
    store = FakeWorkflowRunDeclarationStore(repo)
    return store, store.create(wf.id, 1, None, uuid4()).workflow_run_id


def _get(store: FakeWorkflowRunDeclarationStore, run_id: UUID) -> WorkflowRunView:
    view = store.get(run_id)
    assert view is not None
    return view


def _message(run_id: UUID, **overrides: Any) -> WorkflowRunStatusMessage:
    payload: dict[str, Any] = {
        "workflow_run_id": run_id,
        "seq": 1,
        "status": WorkflowRunStatus.RUNNING,
        "at": datetime(2026, 1, 1, tzinfo=UTC),
    }
    payload.update(overrides)
    return WorkflowRunStatusMessage.model_validate(payload)


def test_higher_seq_is_applied_and_returns_true() -> None:
    store, run_id = _store_with_run()

    applied = ApplyWorkflowRunStatusUseCase(store)(_message(run_id, seq=1))

    assert applied is True
    assert _get(store, run_id).status == WorkflowRunStatus.RUNNING


def test_equal_or_lower_seq_is_ignored_and_returns_false() -> None:
    """spec 0005 2.9 개정 2: `seq` 가 저장값보다 크지 않으면 적용하지 않는다(멱등 무시)."""
    store, run_id = _store_with_run()
    apply = ApplyWorkflowRunStatusUseCase(store)
    apply(_message(run_id, seq=5, status=WorkflowRunStatus.RUNNING))

    lower = apply(_message(run_id, seq=3, status=WorkflowRunStatus.FAILED))
    equal = apply(_message(run_id, seq=5, status=WorkflowRunStatus.FAILED))

    assert (lower, equal) == (False, False)
    assert _get(store, run_id).status == WorkflowRunStatus.RUNNING


def test_absent_optional_fields_keep_previous_values() -> None:
    """`None` 인 선택 필드는 이전 값을 지우지 않는다(`COALESCE(new, old)`)."""
    store, run_id = _store_with_run()
    apply = ApplyWorkflowRunStatusUseCase(store)
    started = datetime(2026, 1, 1, 1, tzinfo=UTC)
    apply(_message(run_id, seq=1, started_at=started, current_node_id="s"))

    apply(_message(run_id, seq=2, status=WorkflowRunStatus.SUCCEEDED))

    view = _get(store, run_id)
    assert view.status == WorkflowRunStatus.SUCCEEDED
    assert view.started_at == started
    assert view.current_node_id == "s"


def test_unknown_run_returns_false() -> None:
    store, _ = _store_with_run()

    assert ApplyWorkflowRunStatusUseCase(store)(_message(uuid4())) is False
