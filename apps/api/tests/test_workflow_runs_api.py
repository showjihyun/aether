"""spec 0005 2.2, 2.3, R-13 (P4-2a A1): Workflow Run HTTP 라우터 — fake 저장소로 컨테이너
없이. `POST /workflows/{id}/runs` 는 202 와 `queued`, 없는 Workflow·Version 은 404 와 서로
다른 코드, `GET /workflow-runs/{id}` 는 200/404 이고 투영된 `waiting_run` 이 본문에 나타납니다.
인증은 `test_routes_require_auth.py` 가 전 경로에 대해 따로 증명합니다.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from aether_api.adapters.inbound.http.workflow_runs import build_workflow_runs_router
from aether_api.application.usecases.get_workflow_run import GetWorkflowRunUseCase
from aether_api.application.usecases.start_workflow_run import StartWorkflowRunUseCase
from aether_api.domain.api_key import Principal
from aether_workflow.domain.node import Edge, Node, NodeKind
from aether_workflow.domain.run_status import WorkflowRunStatus
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from apps.api.tests.fakes_workflow import (
    FakeWorkflowRepository,
    FakeWorkflowRunDeclarationStore,
    FakeWorkflowRunNotifier,
)


def _principal(request: Request) -> Principal:
    del request
    return Principal(key_id=uuid4(), label="unit")


def _client() -> tuple[
    TestClient, FakeWorkflowRepository, FakeWorkflowRunDeclarationStore, FakeWorkflowRunNotifier
]:
    repo = FakeWorkflowRepository()
    store = FakeWorkflowRunDeclarationStore(repo)
    notifier = FakeWorkflowRunNotifier()
    app = FastAPI()
    app.include_router(
        build_workflow_runs_router(
            _principal,
            StartWorkflowRunUseCase(repo, store, notifier),
            GetWorkflowRunUseCase(store),
        )
    )
    return TestClient(app), repo, store, notifier


def _workflow(repo: FakeWorkflowRepository) -> UUID:
    return repo.create(
        "wf", (Node("s", NodeKind.START), Node("e", NodeKind.END)), (Edge("s", "e"),)
    ).id


def test_post_returns_202_with_queued_run() -> None:
    client, repo, store, notifier = _client()
    workflow_id = _workflow(repo)

    response = client.post(f"/workflows/{workflow_id}/runs", json={"input": {"q": "hi"}})

    assert response.status_code == 202, response.text
    body = response.json()
    assert body["status"] == "queued"
    assert body["workflow_id"] == str(workflow_id)
    assert body["workflow_version"] == 1
    run_id = UUID(body["workflow_run_id"])
    assert store.inputs[run_id] == {"q": "hi"}
    assert len(notifier.calls) == 1
    assert body["requested_at"]


def test_post_accepts_null_input_and_explicit_version() -> None:
    client, repo, _store, _notifier = _client()
    workflow_id = _workflow(repo)

    response = client.post(
        f"/workflows/{workflow_id}/runs", json={"input": None, "workflow_version": 1}
    )

    assert response.status_code == 202, response.text


def test_post_rejects_non_object_input() -> None:
    """`input` 은 객체 또는 null — 문자열은 422(FastAPI 요청 검증)."""
    client, repo, _store, _notifier = _client()
    workflow_id = _workflow(repo)

    response = client.post(f"/workflows/{workflow_id}/runs", json={"input": "text"})

    assert response.status_code == 422


def test_post_unknown_workflow_is_404_workflow_not_found() -> None:
    client, _repo, _store, notifier = _client()

    response = client.post(f"/workflows/{uuid4()}/runs", json={"input": None})

    assert response.status_code == 404
    assert response.json() == {"detail": "workflow_not_found"}
    assert notifier.calls == []


def test_post_unknown_version_is_404_workflow_version_not_found() -> None:
    client, repo, _store, notifier = _client()
    workflow_id = _workflow(repo)

    response = client.post(
        f"/workflows/{workflow_id}/runs", json={"input": None, "workflow_version": 9}
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "workflow_version_not_found"}
    assert notifier.calls == []


def test_get_returns_200_with_projection_fields() -> None:
    """spec 0005 R-13: 투영된 `waiting_run` 과 기다리는 자식 Run 이 응답 본문에 나타난다."""
    client, repo, store, _notifier = _client()
    created = store.create(_workflow(repo), 1, None)
    child = uuid4()
    store.apply_status(
        created.workflow_run_id,
        seq=2,
        status=WorkflowRunStatus.WAITING_RUN,
        current_node_id="a",
        waiting_run_id=child,
        started_at=datetime(2026, 1, 1, tzinfo=UTC),
        finished_at=None,
        failure_reason=None,
    )

    response = client.get(f"/workflow-runs/{created.workflow_run_id}")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["workflow_run_id"] == str(created.workflow_run_id)
    assert body["status"] == "waiting_run"
    assert body["waiting_run_id"] == str(child)
    assert body["current_node_id"] == "a"
    assert body["finished_at"] is None
    assert body["failure_reason"] is None
    assert body["workflow_version_id"] == str(created.workflow_version_id)


def test_get_unknown_is_404_workflow_run_not_found() -> None:
    client, _repo, _store, _notifier = _client()

    response = client.get(f"/workflow-runs/{uuid4()}")

    assert response.status_code == 404
    assert response.json() == {"detail": "workflow_run_not_found"}
