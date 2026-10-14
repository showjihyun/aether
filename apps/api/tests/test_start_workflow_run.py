"""spec 0005 2.2, 2.3, 2.9 개정 2 (P4-2a A1): `StartWorkflowRunUseCase` — Version 결정 →
선언(커밋) → 통지. `request_run.py` 와 같은 모양입니다.

`FakeWorkflowRepository`·`FakeWorkflowRunDeclarationStore`·`FakeWorkflowRunNotifier` 로
컨테이너 없이 돕니다. 통지 실패는 삼키고 WARNING 만 남깁니다(202 를 막지 않음).
"""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from aether_api.application.ports.inbound.workflows import (
    DefineWorkflowRequest,
    UpdateWorkflowRequest,
)
from aether_api.application.usecases.define_workflow import DefineWorkflowUseCase
from aether_api.application.usecases.start_workflow_run import StartWorkflowRunUseCase
from aether_api.application.usecases.update_workflow import UpdateWorkflowUseCase
from aether_api.domain.workflow import WorkflowNotFound, WorkflowVersionNotFound
from aether_workflow.domain.node import Edge, Node, NodeKind
from aether_workflow.domain.run_status import WorkflowRunStatus

from apps.api.tests.fakes import FakeRequestTracing
from apps.api.tests.fakes_workflow import (
    FakeWorkflowRepository,
    FakeWorkflowRunDeclarationStore,
    FakeWorkflowRunNotifier,
)

_NODES = (Node("s", NodeKind.START), Node("e", NodeKind.END))
_EDGES = (Edge("s", "e"),)
_KEY = uuid4()
_TRACEPARENT = "00-" + "c" * 32 + "-" + "d" * 16 + "-01"

_Built = tuple[
    StartWorkflowRunUseCase,
    FakeWorkflowRepository,
    FakeWorkflowRunDeclarationStore,
    FakeWorkflowRunNotifier,
]


def _workflow_with_two_versions(repo: FakeWorkflowRepository) -> UUID:
    view = DefineWorkflowUseCase(repo)(DefineWorkflowRequest("wf", _NODES, _EDGES))
    UpdateWorkflowUseCase(repo)(UpdateWorkflowRequest(view.id, _NODES, _EDGES))
    return view.id


def _build(*, notifier: FakeWorkflowRunNotifier | None = None) -> _Built:
    repo = FakeWorkflowRepository()
    store = FakeWorkflowRunDeclarationStore(repo)
    notifier = notifier if notifier is not None else FakeWorkflowRunNotifier()
    return StartWorkflowRunUseCase(repo, store, notifier), repo, store, notifier


def test_defaults_to_current_version_and_starts_queued() -> None:
    """spec 0005 2.2: `workflow_version` 이 없으면 `workflow.current_version`(여기서는 2)."""
    start, repo, _store, _notifier = _build()
    workflow_id = _workflow_with_two_versions(repo)

    view = start(workflow_id, {"k": "v"}, None, _KEY)

    assert view.workflow_id == workflow_id
    assert view.workflow_version == 2
    assert view.status == WorkflowRunStatus.QUEUED


def test_explicit_version_is_used() -> None:
    """spec 0005 2.2: 지정한 Version 으로 실행됩니다(현재 Version 이 아니어도)."""
    start, repo, _store, _notifier = _build()
    workflow_id = _workflow_with_two_versions(repo)

    view = start(workflow_id, None, 1, _KEY)

    assert view.workflow_version == 1


def test_input_is_handed_to_the_store() -> None:
    """spec 0005 2.9: `input` 은 선언 행에 그대로 저장됩니다."""
    start, repo, store, _notifier = _build()
    workflow_id = _workflow_with_two_versions(repo)

    view = start(workflow_id, {"k": [1, 2]}, None, _KEY)

    assert store.inputs[view.workflow_run_id] == {"k": [1, 2]}


def test_unknown_workflow_raises_workflow_not_found() -> None:
    """spec 0005 2.2: 없는 Workflow 는 `WorkflowNotFound`."""
    start, _repo, _store, notifier = _build()

    with pytest.raises(WorkflowNotFound):
        start(uuid4(), None, None, _KEY)
    assert notifier.calls == []


def test_unknown_version_raises_workflow_version_not_found() -> None:
    """spec 0005 2.2: 지정한 Version 이 없으면 `WorkflowVersionNotFound` 이고 선언도 통지도 없다."""
    start, repo, store, notifier = _build()
    workflow_id = _workflow_with_two_versions(repo)

    with pytest.raises(WorkflowVersionNotFound):
        start(workflow_id, None, 3, _KEY)
    assert notifier.calls == []
    assert store.inputs == {}


def test_requester_is_recorded_on_the_declaration() -> None:
    """spec 0005 2.5 개정 3: Workflow 를 시작한 주체가 선언 행에 남는다 -- 자식 Agent Run 이 그것을
    물려받는다(비우면 `GET /runs/{id}` 가 500)."""
    start, repo, store, _notifier = _build()
    workflow_id = _workflow_with_two_versions(repo)

    view = start(workflow_id, None, None, _KEY)

    assert store.requesters[view.workflow_run_id] == _KEY


def test_notifies_once_with_the_declared_run_and_version_id() -> None:
    """spec 0005 2.9 개정 2: 통지는 선언된(커밋된) run id 와 그 Version id 로 정확히 한 번."""
    start, repo, store, notifier = _build()
    workflow_id = _workflow_with_two_versions(repo)

    view = start(workflow_id, None, None, _KEY)

    assert notifier.calls == [(view.workflow_run_id, view.workflow_version_id, None)]
    assert store.get(view.workflow_run_id) is not None


def test_notifier_failure_does_not_block_and_logs_warning(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """spec 0002 2.2 와 같은 규칙: XADD 실패는 202 를 막지 않고 WARNING 만 남긴다."""
    start, repo, store, _notifier = _build(notifier=FakeWorkflowRunNotifier(should_fail=True))
    workflow_id = _workflow_with_two_versions(repo)

    with caplog.at_level("WARNING"):
        view = start(workflow_id, None, None, _KEY)

    assert view.status == WorkflowRunStatus.QUEUED
    assert store.get(view.workflow_run_id) is not None
    assert any(r.levelname == "WARNING" for r in caplog.records)


def test_traceparent_from_tracing_is_sent_with_the_notification() -> None:
    """spec 0002 2.9 와 같은 규칙: span 안에서 낸 traceparent 가 통지에 실린다."""
    repo = FakeWorkflowRepository()
    store = FakeWorkflowRunDeclarationStore(repo)
    notifier = FakeWorkflowRunNotifier()
    tracing = FakeRequestTracing(traceparent=_TRACEPARENT)
    start = StartWorkflowRunUseCase(repo, store, notifier, tracing=tracing)
    workflow_id = _workflow_with_two_versions(repo)

    start(workflow_id, None, None, _KEY)

    assert notifier.calls[0][2] == _TRACEPARENT
    assert [name for name, _ in tracing.opened] == ["workflow_run.request"]
