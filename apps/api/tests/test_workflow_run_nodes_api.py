"""spec 0007 2.3, 2.4, R-5, D-3, D-4 (P5-2): `GET /workflow-runs/{id}/nodes` 의 HTTP 계약 - fake 로.

`GET /agents` 의 페이지 규칙(`limit` 기본 50·1~200, `cursor`, `{items, next_cursor}`)을 따른다.
인증은 `test_routes_require_auth.py` 가 전 경로에 대해 따로 증명한다.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from aether_api.adapters.inbound.http.workflow_run_nodes import build_workflow_run_nodes_router
from aether_api.application.usecases.list_workflow_run_nodes import ListWorkflowRunNodesUseCase
from aether_api.domain.api_key import Principal
from aether_api.domain.workflow_node_state import WorkflowNodeStateView
from aether_workflow.domain.node import Edge, Node, NodeKind
from aether_workflow.domain.node_execution import NodeExecutionStatus
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from apps.api.tests.fakes_workflow import (
    FakeWorkflowNodeStateStore,
    FakeWorkflowRepository,
    FakeWorkflowRunDeclarationStore,
)

_KEY = uuid4()
_T0 = datetime(2026, 10, 22, 9, 0, tzinfo=UTC)


def _principal(request: Request) -> Principal:
    del request
    return Principal(key_id=_KEY, label="unit")


def _setup() -> tuple[TestClient, FakeWorkflowNodeStateStore, UUID]:
    workflows = FakeWorkflowRepository()
    runs = FakeWorkflowRunDeclarationStore(workflows)
    nodes = FakeWorkflowNodeStateStore()
    wf = workflows.create(
        "wf", (Node("s", NodeKind.START), Node("e", NodeKind.END)), (Edge("s", "e"),)
    )
    run = runs.create(wf.id, 1, None, _KEY)
    app = FastAPI()
    app.include_router(
        build_workflow_run_nodes_router(_principal, ListWorkflowRunNodesUseCase(runs, nodes))
    )
    return TestClient(app), nodes, run.workflow_run_id


def _view(
    node_id: str,
    status: NodeExecutionStatus = NodeExecutionStatus.SUCCEEDED,
    failure_reason: str | None = None,
) -> WorkflowNodeStateView:
    return WorkflowNodeStateView(
        node_id=node_id,
        kind="agent",
        status=status,
        started_at=_T0,
        finished_at=_T0,
        failure_reason=failure_reason,
    )


def test_returns_200_with_page_shape_and_no_output() -> None:
    """R-5, D-4: 200 과 {items, next_cursor}. 항목 열은 상태·시각·사유뿐 - output 이 없다."""
    client, nodes, run = _setup()
    nodes.put(run, _view("a", NodeExecutionStatus.FAILED, "boom"))

    response = client.get(f"/workflow-runs/{run}/nodes")

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"items", "next_cursor"} and body["next_cursor"] is None
    assert body["items"] == [
        {
            "node_id": "a",
            "kind": "agent",
            "status": "failed",
            "started_at": "2026-10-22T09:00:00Z",
            "finished_at": "2026-10-22T09:00:00Z",
            "failure_reason": "boom",
        }
    ]


def test_empty_list_is_200() -> None:
    """R-5: 노드가 없는 Run 은 200 + 빈 items."""
    client, _nodes, run = _setup()

    response = client.get(f"/workflow-runs/{run}/nodes")

    assert response.status_code == 200
    assert response.json() == {"items": [], "next_cursor": None}


def test_unknown_run_is_404() -> None:
    """R-5: 없는 Workflow Run 은 404 workflow_run_not_found."""
    client, _nodes, _run = _setup()

    response = client.get(f"/workflow-runs/{uuid4()}/nodes")

    assert response.status_code == 404
    assert response.json() == {"detail": "workflow_run_not_found"}


def test_limit_and_cursor_walk_all_pages() -> None:
    """spec 0006 D-3: limit 으로 쪼개고 next_cursor 로 끝까지 - 빠짐도 겹침도 없다."""
    client, nodes, run = _setup()
    for node_id in "abcde":
        nodes.put(run, _view(node_id))

    seen: list[str] = []
    cursor: str | None = None
    for _ in range(5):
        params: dict[str, str | int] = {"limit": 2}
        if cursor:
            params["cursor"] = cursor
        body = client.get(f"/workflow-runs/{run}/nodes", params=params).json()
        seen += [i["node_id"] for i in body["items"]]
        cursor = body["next_cursor"]
        if cursor is None:
            break

    assert seen == list("abcde")


def test_limit_out_of_range_and_bad_cursor_are_422() -> None:
    """spec 0006 2.3: limit 은 1~200, 깨진 cursor 는 invalid_cursor 422."""
    client, _nodes, run = _setup()

    assert client.get(f"/workflow-runs/{run}/nodes", params={"limit": 0}).status_code == 422
    assert client.get(f"/workflow-runs/{run}/nodes", params={"limit": 201}).status_code == 422
    bad = client.get(f"/workflow-runs/{run}/nodes", params={"cursor": "!!not-base64!!"})
    assert bad.status_code == 422 and bad.json() == {"detail": "invalid_cursor"}
