"""spec 0007 2.3, 2.4, R-5, D-3, D-4 (P5-2): `GET /workflow-runs/{id}/nodes` - 실제 PostgreSQL.

`api-integration`. 증명하는 것:

1. 투영(`control.workflow_node_states`)의 행이 200 과 페이지 모양으로 나온다 - 행 N개를 limit 2 로
   전부 훑어 N개가 정확히 한 번씩(커서 왕복이 행을 빠뜨리지 않는다). 다른 Run 의 노드는 안 섞인다.
2. 노드가 없는 Run 은 200 + 빈 목록, 없는 Run 은 404, 인증 없으면 401.
3. 응답 항목에는 `output` 이 없다(D-4). 이 앱은 `aether_control` 로 붙어 있고 그 역할은 `data` 에
   권한이 없으므로(0001 R-7) `data` 를 읽으려 했다면 permission denied 로 깨졌을 것이다.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import psycopg
import pytest
from aether_api.adapters.outbound.db.api_keys import PostgresApiKeyStore
from aether_api.adapters.outbound.db.workflow_node_state_projection_store import (
    PostgresWorkflowNodeStateProjectionStore,
)
from aether_api.application.usecases.issue_api_key import IssueApiKeyUseCase
from aether_api.domain.workflow_node_status_message import WorkflowNodeStatusMessage
from aether_api.main import create_app
from aether_api.settings import Settings
from aether_workflow.domain.node_execution import NodeExecutionStatus
from fastapi.testclient import TestClient

pytestmark = pytest.mark.integration

Connect = Callable[[], psycopg.Connection]
_T0 = datetime(2026, 10, 22, 9, 0, tzinfo=UTC)


@pytest.fixture
def client(control_database_url: str, redis_url: str) -> TestClient:
    return TestClient(create_app(Settings(database_url=control_database_url, redis_url=redis_url)))


@pytest.fixture
def headers(control_connection_factory: Connect) -> dict[str, str]:
    issued = IssueApiKeyUseCase(PostgresApiKeyStore(control_connection_factory))(
        f"test-nodes-{uuid4()}"
    )
    return {"Authorization": f"Bearer {issued.raw_key}"}


def _seed_run(admin_connection_factory: Connect) -> UUID:
    conn = admin_connection_factory()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO control.workflows (name) VALUES (%s) RETURNING id",
                (f"wf-{uuid.uuid4()}",),
            )
            row = cur.fetchone()
            assert row is not None
            cur.execute(
                "INSERT INTO control.workflow_versions (workflow_id, version, nodes, edges) "
                "VALUES (%s, 1, '[]', '[]') RETURNING id",
                (row[0],),
            )
            version = cur.fetchone()
            assert version is not None
            cur.execute(
                "INSERT INTO control.workflow_runs (workflow_version_id) VALUES (%s) RETURNING id",
                (version[0],),
            )
            run = cur.fetchone()
            assert run is not None
            run_id: UUID = run[0]
        conn.commit()
        return run_id
    finally:
        conn.close()


def _apply(
    control_connection_factory: Connect,
    run_id: UUID,
    node_id: str,
    status: NodeExecutionStatus,
    seq: int,
    **extra: Any,
) -> None:
    store = PostgresWorkflowNodeStateProjectionStore(control_connection_factory)
    assert store.apply_status(
        WorkflowNodeStatusMessage(
            workflow_run_id=run_id,
            node_id=node_id,
            kind="agent",
            status=status,
            status_seq=seq,
            **extra,
        )
    )


def test_lists_the_projection_rows_and_walks_every_page_once(
    client: TestClient,
    headers: dict[str, str],
    admin_connection_factory: Connect,
    control_connection_factory: Connect,
) -> None:
    """R-5: 200 과 페이지 모양, 5행을 limit 2 로 훑어 정확히 한 번씩, 다른 Run 은 섞이지 않음."""
    run, other = _seed_run(admin_connection_factory), _seed_run(admin_connection_factory)
    for i, node_id in enumerate("edcba"):
        _apply(control_connection_factory, run, node_id, NodeExecutionStatus.RUNNING, i + 1)
    _apply(control_connection_factory, other, "zzz", NodeExecutionStatus.RUNNING, 1)

    seen: list[dict[str, Any]] = []
    cursor: str | None = None
    for _ in range(10):
        params: dict[str, Any] = {"limit": 2}
        if cursor:
            params["cursor"] = cursor
        response = client.get(f"/workflow-runs/{run}/nodes", params=params, headers=headers)
        assert response.status_code == 200, response.text
        body = response.json()
        assert set(body) == {"items", "next_cursor"}
        seen += body["items"]
        cursor = body["next_cursor"]
        if cursor is None:
            break

    assert [n["node_id"] for n in seen] == list("abcde")
    assert all("output" not in n for n in seen)
    assert set(seen[0]) == {
        "node_id",
        "kind",
        "status",
        "started_at",
        "finished_at",
        "failure_reason",
    }


def test_failed_node_carries_status_times_and_reason(
    client: TestClient,
    headers: dict[str, str],
    admin_connection_factory: Connect,
    control_connection_factory: Connect,
) -> None:
    """R-6 의 근거: 실패한 노드의 상태·시각·사유가 그대로 나온다."""
    run = _seed_run(admin_connection_factory)
    _apply(
        control_connection_factory,
        run,
        "n1",
        NodeExecutionStatus.FAILED,
        3,
        started_at=_T0,
        finished_at=_T0,
        failure_reason="child_run_failed",
    )

    item = client.get(f"/workflow-runs/{run}/nodes", headers=headers).json()["items"][0]

    assert item["status"] == "failed" and item["failure_reason"] == "child_run_failed"
    assert item["started_at"].startswith("2026-10-22T09:00:00")
    assert item["finished_at"].startswith("2026-10-22T09:00:00")


def test_run_without_nodes_is_200_empty_and_unknown_run_is_404(
    client: TestClient, headers: dict[str, str], admin_connection_factory: Connect
) -> None:
    """R-5: 빈 목록도 200, 없는 Run 은 404."""
    run = _seed_run(admin_connection_factory)

    empty = client.get(f"/workflow-runs/{run}/nodes", headers=headers)
    missing = client.get(f"/workflow-runs/{uuid4()}/nodes", headers=headers)

    assert empty.status_code == 200 and empty.json() == {"items": [], "next_cursor": None}
    assert missing.status_code == 404 and missing.json() == {"detail": "workflow_run_not_found"}


def test_requires_authentication(client: TestClient) -> None:
    """R-8: 인증 없으면 401."""
    assert client.get(f"/workflow-runs/{uuid4()}/nodes").status_code == 401


def test_bad_cursor_is_422(
    client: TestClient, headers: dict[str, str], admin_connection_factory: Connect
) -> None:
    """spec 0006 2.3: 깨진 cursor 는 500 이 아니라 422."""
    run = _seed_run(admin_connection_factory)

    response = client.get(f"/workflow-runs/{run}/nodes", params={"cursor": "!!"}, headers=headers)

    assert response.status_code == 422
