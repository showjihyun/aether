"""spec 0006 2.3, D-3, D-11, R-4: 목록 경로 다섯 - 실제 PostgreSQL, api 역할.

`api-integration`. 커서 왕복이 행을 빠뜨리지 않는지(행 N개를 limit 2 로 전부 훑어 N개가 정확히 한
번씩), 상태 필터가 SQL 에서 걸리는지, 그리고 `GET /workflow-runs` 가 `data` 평면을 읽지 않는지를
판정합니다. 마지막은 접속 역할이 증거입니다 - 이 앱은 `aether_control` 로 붙어 있고, 그 역할은
`data` 스키마에 권한이 없으므로(마이그레이션 0001 R-7) 읽으려 했다면 permission denied 로 깨졌을
것입니다. 세션 안에서 DB 를 다른 테스트와 공유하므로 시드한 행만 골라 셉니다.
"""

from __future__ import annotations

import base64
from collections.abc import Callable
from typing import Any
from uuid import UUID, uuid4

import psycopg
import pytest
from aether_api.adapters.outbound.db.agent_repository import PostgresAgentRepository
from aether_api.adapters.outbound.db.api_keys import PostgresApiKeyStore
from aether_api.adapters.outbound.db.knowledge_declaration_store import (
    PostgresKnowledgeDeclarationStore,
)
from aether_api.adapters.outbound.db.run_declaration_store import PostgresRunDeclarationStore
from aether_api.adapters.outbound.db.workflow_repository import PostgresWorkflowRepository
from aether_api.adapters.outbound.db.workflow_run_declaration_store import (
    PostgresWorkflowRunDeclarationStore,
)
from aether_api.application.usecases.issue_api_key import IssueApiKeyUseCase
from aether_api.main import create_app
from aether_api.settings import Settings
from aether_runtime.domain.agent import AgentDefinition
from aether_runtime.domain.run import RunStatus
from aether_workflow.domain.node import Edge, Node, NodeKind
from aether_workflow.domain.run_status import WorkflowRunStatus
from fastapi.testclient import TestClient

pytestmark = pytest.mark.integration

Connect = Callable[[], psycopg.Connection]


@pytest.fixture
def client(control_database_url: str, redis_url: str) -> TestClient:
    return TestClient(create_app(Settings(database_url=control_database_url, redis_url=redis_url)))


@pytest.fixture
def key(control_connection_factory: Connect) -> tuple[dict[str, str], UUID]:
    issued = IssueApiKeyUseCase(PostgresApiKeyStore(control_connection_factory))(
        f"test-list-{uuid4()}"
    )
    return {"Authorization": f"Bearer {issued.raw_key}"}, issued.key.id


def _walk(
    client: TestClient, path: str, headers: dict[str, str], limit: int = 2, **params: Any
) -> list[dict[str, Any]]:
    """`next_cursor` 가 null 이 될 때까지 훑어 모든 항목을 순서대로 돌려줍니다."""
    items: list[dict[str, Any]] = []
    cursor: str | None = None
    for _ in range(500):
        query = {"limit": limit, **params, **({"cursor": cursor} if cursor else {})}
        response = client.get(path, params=query, headers=headers)
        assert response.status_code == 200, response.text
        body = response.json()
        items.extend(body["items"])
        cursor = body["next_cursor"]
        if cursor is None:
            return items
    raise AssertionError("next_cursor never became null")


def _seed_runs(connect: Connect, requested_by: UUID, count: int) -> list[UUID]:
    agent = PostgresAgentRepository(connect).create(
        f"list-agent-{uuid4()}",
        AgentDefinition.model_validate({"schema_version": 1, "system_prompt": "p"}),
    )
    with connect() as conn, conn.cursor() as cur:
        cur.execute("SELECT id FROM control.agent_versions WHERE agent_id = %s", (agent.id,))
        row = cur.fetchone()
    assert row is not None
    store = PostgresRunDeclarationStore(connect)
    return [store.create(agent.id, row[0], 1, "in", requested_by).run_id for _ in range(count)]


def test_runs_cursor_walk_returns_every_row_exactly_once(
    client: TestClient, key: tuple[dict[str, str], UUID], control_connection_factory: Connect
) -> None:
    """spec 0006 R-4: 행 N 개를 limit 2 로 전부 훑으면 N 개가 정확히 한 번씩 나온다."""
    headers, key_id = key
    seeded = {str(i) for i in _seed_runs(control_connection_factory, key_id, 7)}

    items = _walk(client, "/runs", headers)

    seen = [item["run_id"] for item in items]
    assert len(seen) == len(set(seen)), "같은 행이 두 번 나왔다"
    assert seeded <= set(seen), "시드한 행이 빠졌다"


def test_runs_status_filter_is_applied_in_sql(
    client: TestClient, key: tuple[dict[str, str], UUID], control_connection_factory: Connect
) -> None:
    """spec 0006 2.3: 필터가 걸리면 그 상태만 나오고(다른 상태는 안 나오고), 커서도 이어진다."""
    headers, key_id = key
    run_ids = _seed_runs(control_connection_factory, key_id, 5)
    store = PostgresRunDeclarationStore(control_connection_factory)
    running = run_ids[:3]
    for seq, run_id in enumerate(running, start=1):
        assert store.apply_status(
            run_id,
            seq=seq,
            status=RunStatus.RUNNING,
            started_at=None,
            finished_at=None,
            failure_reason=None,
            trace_id=None,
        )

    items = _walk(client, "/runs", headers, status="running")

    assert {item["status"] for item in items} == {"running"}
    assert {str(r) for r in running} <= {item["run_id"] for item in items}
    assert not ({str(r) for r in run_ids[3:]} & {item["run_id"] for item in items})


def test_runs_list_survives_child_runs_without_requester(
    client: TestClient, key: tuple[dict[str, str], UUID], control_connection_factory: Connect
) -> None:
    """spec 0006 2.3: Workflow 가 선언한 자식 Run 은 `requested_by` 가 NULL 이다 - 목록은 500 이
    아니라 그 행을 `requested_by: null` 로 돌려준다(`GET /runs/{id}` 와 달리 목록 하나가 전체를
    깨뜨리면 안 된다)."""
    headers, key_id = key
    parent = _seed_runs(control_connection_factory, key_id, 1)[0]
    with control_connection_factory() as conn, conn.cursor() as cur:
        cur.execute("SELECT agent_version_id FROM control.runs WHERE id = %s", (parent,))
        row = cur.fetchone()
    assert row is not None
    child = uuid4()
    assert PostgresRunDeclarationStore(control_connection_factory).create_with_id(
        child, row[0], "in", None
    )

    items = _walk(client, "/runs", headers)

    by_id = {item["run_id"]: item for item in items}
    assert by_id[str(child)]["requested_by"] is None
    assert by_id[str(parent)]["requested_by"] == str(key_id)


def test_workflows_cursor_walk_returns_every_row_exactly_once(
    client: TestClient, key: tuple[dict[str, str], UUID], control_connection_factory: Connect
) -> None:
    """spec 0006 R-4: Workflow 정의 N 개를 limit 2 로 훑으면 N 개가 한 번씩, 이름·버전 포함."""
    headers, _ = key
    repo = PostgresWorkflowRepository(control_connection_factory)
    nodes = (Node("s", NodeKind.START), Node("e", NodeKind.END))
    seeded = {
        str(repo.create(f"wf-{uuid4()}", nodes, (Edge("s", "e"),)).id): None for _ in range(5)
    }

    items = _walk(client, "/workflows", headers)

    seen = [item["id"] for item in items]
    assert len(seen) == len(set(seen))
    assert set(seeded) <= set(seen)
    assert all(item["current_version"] == 1 for item in items if item["id"] in seeded)


def test_workflow_runs_cursor_walk_and_filter_under_api_role(
    client: TestClient, key: tuple[dict[str, str], UUID], control_connection_factory: Connect
) -> None:
    """spec 0006 R-4, D-4: `control.workflow_runs` 투영만 읽는다 - api 역할(`data` 권한 없음)로
    붙은 채 통과하는 것이 `data` 를 읽지 않는다는 증거다. 커서 왕복과 상태 필터도 판정한다."""
    headers, key_id = key
    repo = PostgresWorkflowRepository(control_connection_factory)
    store = PostgresWorkflowRunDeclarationStore(control_connection_factory)
    workflow = repo.create(
        f"wf-{uuid4()}",
        (Node("s", NodeKind.START), Node("e", NodeKind.END)),
        (Edge("s", "e"),),
    )
    runs = [store.create(workflow.id, 1, None, key_id).workflow_run_id for _ in range(5)]
    for run_id in runs[:2]:
        assert store.apply_status(
            run_id,
            seq=1,
            status=WorkflowRunStatus.RUNNING,
            current_node_id="s",
            waiting_run_id=None,
            started_at=None,
            finished_at=None,
            failure_reason=None,
        )

    everything = _walk(client, "/workflow-runs", headers)
    running = _walk(client, "/workflow-runs", headers, status="running")

    seen = [item["workflow_run_id"] for item in everything]
    assert len(seen) == len(set(seen))
    assert {str(r) for r in runs} <= set(seen)
    assert {item["status"] for item in running} == {"running"}
    assert {str(r) for r in runs[:2]} <= {item["workflow_run_id"] for item in running}
    assert not ({str(r) for r in runs[2:]} & {item["workflow_run_id"] for item in running})


def test_knowledge_sets_and_ingestions_cursor_walk(
    client: TestClient, key: tuple[dict[str, str], UUID], control_connection_factory: Connect
) -> None:
    """spec 0006 R-4: 세트 N 개, 한 세트의 적재 M 개가 각각 한 번씩 나오고 적재는 그 세트의 것만."""
    headers, _ = key
    store = PostgresKnowledgeDeclarationStore(control_connection_factory)
    sets = [store.create_set(f"set-{uuid4()}") for _ in range(5)]
    mine, other = sets[0], sets[1]
    ingestions = [store.create_ingestion(mine.id, f"/d/{i}") for i in range(5)]
    store.create_ingestion(other.id, "/other")
    for ingestion in ingestions[:2]:
        assert store.apply_ingestion_status(
            ingestion.id,
            status="succeeded",
            started_at=None,
            finished_at=None,
            failure_reason=None,
        )

    set_items = _walk(client, "/knowledge-sets", headers)
    ingestion_items = _walk(client, f"/knowledge-sets/{mine.id}/ingestions", headers)
    succeeded = _walk(client, f"/knowledge-sets/{mine.id}/ingestions", headers, status="succeeded")

    seen_sets = [item["id"] for item in set_items]
    assert len(seen_sets) == len(set(seen_sets))
    assert {str(s.id) for s in sets} <= set(seen_sets)
    assert sorted(item["ingestion_id"] for item in ingestion_items) == sorted(
        str(i.id) for i in ingestions
    )
    assert {item["knowledge_set_id"] for item in ingestion_items} == {str(mine.id)}
    assert sorted(item["ingestion_id"] for item in succeeded) == sorted(
        str(i.id) for i in ingestions[:2]
    )


def test_list_paths_are_200_when_empty_and_401_without_key(
    client: TestClient, key: tuple[dict[str, str], UUID], control_connection_factory: Connect
) -> None:
    """spec 0006 R-4: 인증이 없으면 다섯 경로 모두 401, 빈 세트의 적재 목록은 200."""
    headers, _ = key
    empty_set = PostgresKnowledgeDeclarationStore(control_connection_factory).create_set("e")
    paths = [
        "/runs",
        "/workflows",
        "/workflow-runs",
        "/knowledge-sets",
        f"/knowledge-sets/{empty_set.id}/ingestions",
    ]

    for path in paths:
        assert client.get(path).status_code == 401, path
        assert client.get(path, headers=headers).status_code == 200, path

    body = client.get(paths[-1], headers=headers).json()
    assert body == {"items": [], "next_cursor": None}


def test_newest_first_for_runs_workflow_runs_and_ingestions(
    client: TestClient, key: tuple[dict[str, str], UUID], control_connection_factory: Connect
) -> None:
    """spec 0006 2.3: 세 경로는 최신 것부터 - 시드를 만든 순서의 역순으로 나오고, 커서(`<`)로 쪽을
    넘겨도 방향이 이어져 행을 빠뜨리지 않는다. 오름차순인 두 경로는 만든 순서대로."""
    headers, key_id = key
    runs = [str(r) for r in _seed_runs(control_connection_factory, key_id, 5)]
    wf_repo = PostgresWorkflowRepository(control_connection_factory)
    wf_store = PostgresWorkflowRunDeclarationStore(control_connection_factory)
    nodes = (Node("s", NodeKind.START), Node("e", NodeKind.END))
    workflows = [wf_repo.create(f"wf-{uuid4()}", nodes, (Edge("s", "e"),)) for _ in range(3)]
    wf_runs = [
        str(wf_store.create(workflows[0].id, 1, None, key_id).workflow_run_id) for _ in range(5)
    ]
    k_store = PostgresKnowledgeDeclarationStore(control_connection_factory)
    knowledge_set = k_store.create_set(f"set-{uuid4()}")
    ingestions = [str(k_store.create_ingestion(knowledge_set.id, f"/{i}").id) for i in range(5)]

    def order(path: str, id_key: str, mine: list[str]) -> list[str]:
        return [i[id_key] for i in _walk(client, path, headers) if i[id_key] in mine]

    assert order("/runs", "run_id", runs) == runs[::-1]
    assert order("/workflow-runs", "workflow_run_id", wf_runs) == wf_runs[::-1]
    assert (
        order(f"/knowledge-sets/{knowledge_set.id}/ingestions", "ingestion_id", ingestions)
        == ingestions[::-1]
    )
    assert order("/workflows", "id", [str(w.id) for w in workflows]) == [
        str(w.id) for w in workflows
    ]
    newest_first_page = client.get("/runs", params={"limit": 1}, headers=headers).json()["items"]
    assert newest_first_page[0]["run_id"] not in runs[:-1], "첫 항목이 가장 오래된 시드일 수 없다"


@pytest.mark.parametrize(
    "bad",
    [
        "",
        "!!not-base64!!",
        base64.urlsafe_b64encode(b"garbage").decode("ascii"),
        base64.urlsafe_b64encode(b"not-a-date|not-a-uuid").decode("ascii"),
        base64.urlsafe_b64encode(b"2026-01-01T00:00:00+00:00|x").decode("ascii"),
        "안녕",
    ],
    ids=["empty", "not-base64", "no-separator", "bad-date", "bad-uuid", "non-ascii"],
)
def test_malformed_cursor_is_422_on_all_six_paths(
    bad: str,
    client: TestClient,
    key: tuple[dict[str, str], UUID],
    control_connection_factory: Connect,
) -> None:
    """spec 0006 2.3: 깨진 커서는 실제 PostgreSQL 에서도 여섯 경로(`/agents` 포함) 모두 422."""
    headers, _ = key
    knowledge_set = PostgresKnowledgeDeclarationStore(control_connection_factory).create_set(
        f"c-{uuid4()}"
    )
    paths = [
        "/agents",
        "/runs",
        "/workflows",
        "/workflow-runs",
        "/knowledge-sets",
        f"/knowledge-sets/{knowledge_set.id}/ingestions",
    ]

    for path in paths:
        response = client.get(path, params={"cursor": bad}, headers=headers)
        assert response.status_code == 422, (path, response.status_code, response.text)


def test_get_run_detail_survives_child_run_without_requester(
    client: TestClient, key: tuple[dict[str, str], UUID], control_connection_factory: Connect
) -> None:
    """MVP-2b (A), spec 0006 2.3: Workflow 가 선언한 자식 Run 은 `requested_by` 가 NULL 이다 -
    상세는 500 이 아니라 200 이고 그 필드가 `null` 이다."""
    headers, key_id = key
    parent = _seed_runs(control_connection_factory, key_id, 1)[0]
    with control_connection_factory() as conn, conn.cursor() as cur:
        cur.execute("SELECT agent_version_id FROM control.runs WHERE id = %s", (parent,))
        row = cur.fetchone()
    assert row is not None
    child = uuid4()
    assert PostgresRunDeclarationStore(control_connection_factory).create_with_id(
        child, row[0], "in", None
    )

    response = client.get(f"/runs/{child}", headers=headers)

    assert response.status_code == 200
    assert response.json()["requested_by"] is None
    assert client.get(f"/runs/{parent}", headers=headers).json()["requested_by"] == str(key_id)
