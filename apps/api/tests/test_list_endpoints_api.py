"""spec 0006 2.3, D-3, D-11, R-4: 목록 경로 다섯의 HTTP 계약 — fake 저장소로 컨테이너 없이.

`GET /agents` 의 페이지 규칙(`limit` 기본 50·1~200, `cursor`, `{items, next_cursor}`)을
그대로 따릅니다. 필터는 상태 하나까지(`status`) - 상태가 없는 목록(workflows·knowledge-sets)
에는 필터가 없습니다. 인증은 `test_routes_require_auth.py` 가 전 경로에 대해 따로 증명합니다.
"""

from __future__ import annotations

import base64
import itertools
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import pytest
from aether_api.adapters.inbound.http.agents import build_agents_router
from aether_api.adapters.inbound.http.listings import build_listings_router
from aether_api.application.usecases.create_agent import CreateAgentUseCase
from aether_api.application.usecases.get_agent import GetAgentUseCase
from aether_api.application.usecases.get_agent_version import GetAgentVersionUseCase
from aether_api.application.usecases.list_agents import ListAgentsUseCase
from aether_api.application.usecases.list_ingestions import ListIngestionsUseCase
from aether_api.application.usecases.list_knowledge_sets import ListKnowledgeSetsUseCase
from aether_api.application.usecases.list_runs import ListRunsUseCase
from aether_api.application.usecases.list_workflow_runs import ListWorkflowRunsUseCase
from aether_api.application.usecases.list_workflows import ListWorkflowsUseCase
from aether_api.application.usecases.update_agent import UpdateAgentUseCase
from aether_api.domain.api_key import Principal
from aether_runtime.domain.run import RunStatus
from aether_workflow.domain.node import Edge, Node, NodeKind
from aether_workflow.domain.run_status import WorkflowRunStatus
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from apps.api.tests.fakes import FakeAgentRepository, FakeRunDeclarationStore
from apps.api.tests.fakes_knowledge import FakeKnowledgeDeclarationStore
from apps.api.tests.fakes_workflow import FakeWorkflowRepository, FakeWorkflowRunDeclarationStore

_KEY = uuid4()


def _principal(request: Request) -> Principal:
    del request
    return Principal(key_id=_KEY, label="unit")


def _clock() -> Callable[[], datetime]:
    """부를 때마다 1초씩 늘어나는 시계 - 정렬 방향 단언이 결정적이도록."""
    ticks = itertools.count(1)
    return lambda: datetime(2026, 1, 1, tzinfo=UTC) + timedelta(seconds=next(ticks))


@dataclass
class _World:
    """다섯 목록이 읽는 fake 저장소 넷과 시드 도우미."""

    runs: FakeRunDeclarationStore = field(default_factory=lambda: FakeRunDeclarationStore(_clock()))
    workflows: FakeWorkflowRepository = field(default_factory=FakeWorkflowRepository)
    knowledge: FakeKnowledgeDeclarationStore = field(default_factory=FakeKnowledgeDeclarationStore)
    workflow_runs: FakeWorkflowRunDeclarationStore = field(init=False)
    _fixed_set: UUID | None = field(default=None, init=False)

    def __post_init__(self) -> None:
        self.workflow_runs = FakeWorkflowRunDeclarationStore(self.workflows)

    @property
    def fixed_set(self) -> UUID:
        """적재 시드가 매달리는 집합 - 처음 쓸 때 만든다(세트 목록 테스트를 오염시키지 않도록)."""
        if self._fixed_set is None:
            self._fixed_set = self.knowledge.create_set("fixed").id
        return self._fixed_set

    def client(self) -> TestClient:
        app = FastAPI()
        app.include_router(
            build_listings_router(
                _principal,
                ListRunsUseCase(self.runs),
                ListWorkflowsUseCase(self.workflows),
                ListWorkflowRunsUseCase(self.workflow_runs),
                ListKnowledgeSetsUseCase(self.knowledge),
                ListIngestionsUseCase(self.knowledge),
            )
        )
        return TestClient(app)

    def add_run(self, status: str = "queued") -> str:
        view = self.runs.create(uuid4(), uuid4(), 1, "in", _KEY)
        if status != "queued":
            self.runs.apply_status(
                view.run_id,
                seq=1,
                status=RunStatus(status),
                started_at=None,
                finished_at=None,
                failure_reason=None,
                trace_id=None,
            )
        return str(view.run_id)

    def add_workflow(self) -> UUID:
        return self.workflows.create(
            f"wf-{uuid4()}", (Node("s", NodeKind.START), Node("e", NodeKind.END)), (Edge("s", "e"),)
        ).id

    def add_workflow_run(self, status: str = "queued") -> str:
        view = self.workflow_runs.create(self.add_workflow(), 1, None, _KEY)
        if status != "queued":
            self.workflow_runs.apply_status(
                view.workflow_run_id,
                seq=1,
                status=WorkflowRunStatus(status),
                current_node_id=None,
                waiting_run_id=None,
                started_at=None,
                finished_at=None,
                failure_reason=None,
            )
        return str(view.workflow_run_id)

    def add_set(self) -> str:
        return str(self.knowledge.create_set(f"set-{uuid4()}").id)

    def add_ingestion(self, status: str = "queued") -> str:
        view = self.knowledge.create_ingestion(self.fixed_set, "/data")
        if status != "queued":
            self.knowledge.apply_ingestion_status(
                view.id,
                status=status,  # type: ignore[arg-type]
                started_at=None,
                finished_at=None,
                failure_reason=None,
            )
        return str(view.id)


@dataclass(frozen=True)
class _Case:
    name: str
    path: str
    id_key: str
    item_keys: frozenset[str]
    add: Callable[[_World, str], str]
    statuses: tuple[str, str] | None = None
    newest_first: bool = False


_RUN_KEYS = frozenset(
    {
        "run_id",
        "agent_id",
        "agent_version",
        "status",
        "requested_at",
        "requested_by",
        "started_at",
        "finished_at",
        "failure_reason",
        "trace_id",
        "cancel_requested_at",
    }
)
_WORKFLOW_RUN_KEYS = frozenset(
    {
        "workflow_run_id",
        "workflow_id",
        "workflow_version",
        "workflow_version_id",
        "status",
        "current_node_id",
        "waiting_run_id",
        "waiting_node_execution_id",
        "wake_at",
        "requested_at",
        "started_at",
        "finished_at",
        "failure_reason",
    }
)
_INGESTION_KEYS = frozenset(
    {
        "ingestion_id",
        "knowledge_set_id",
        "source",
        "status",
        "requested_at",
        "started_at",
        "finished_at",
        "failure_reason",
    }
)

_CASES = [
    _Case(
        "runs", "/runs", "run_id", _RUN_KEYS, lambda w, s: w.add_run(s), ("queued", "running"), True
    ),
    _Case(
        "workflows",
        "/workflows",
        "id",
        frozenset({"id", "name", "current_version", "created_at", "updated_at"}),
        lambda w, s: str(w.add_workflow()),
    ),
    _Case(
        "workflow-runs",
        "/workflow-runs",
        "workflow_run_id",
        _WORKFLOW_RUN_KEYS,
        lambda w, s: w.add_workflow_run(s),
        ("queued", "running"),
        True,
    ),
    _Case(
        "knowledge-sets",
        "/knowledge-sets",
        "id",
        frozenset({"id", "name", "created_at"}),
        lambda w, s: w.add_set(),
    ),
    _Case(
        "ingestions",
        "/knowledge-sets/{set_id}/ingestions",
        "ingestion_id",
        _INGESTION_KEYS,
        lambda w, s: w.add_ingestion(s),
        ("queued", "succeeded"),
        True,
    ),
]
_IDS = [c.name for c in _CASES]
_FILTERED = [c for c in _CASES if c.statuses]


def _setup(case: _Case) -> tuple[_World, TestClient, str]:
    world = _World()
    path = case.path.format(set_id=world.fixed_set) if "{set_id}" in case.path else case.path
    return world, world.client(), path


def _all_pages(
    client: TestClient, path: str, limit: int, **params: Any
) -> list[list[dict[str, Any]]]:
    pages: list[list[dict[str, Any]]] = []
    cursor: str | None = None
    for _ in range(50):
        query = {"limit": limit, **params, **({"cursor": cursor} if cursor else {})}
        body = client.get(path, params=query).json()
        pages.append(body["items"])
        cursor = body["next_cursor"]
        if cursor is None:
            return pages
    raise AssertionError("next_cursor never became null")


@pytest.mark.parametrize("case", _CASES, ids=_IDS)
def test_empty_list_is_200_with_empty_items(case: _Case) -> None:
    """spec 0006 R-4: 빈 목록은 404 가 아니라 200 과 `items: []`, `next_cursor: null`."""
    _world, client, path = _setup(case)

    response = client.get(path)

    assert response.status_code == 200, response.text
    assert response.json() == {"items": [], "next_cursor": None}


@pytest.mark.parametrize("case", _CASES, ids=_IDS)
def test_item_has_exactly_the_documented_fields(case: _Case) -> None:
    """spec 0006 2.3: 항목의 필드 집합이 응답 모델 그대로다(표면을 넓히지 않는다)."""
    world, client, path = _setup(case)
    added = case.add(world, "queued")

    items = client.get(path).json()["items"]

    assert [item[case.id_key] for item in items] == [added]
    assert set(items[0].keys()) == case.item_keys


@pytest.mark.parametrize("case", _CASES, ids=_IDS)
def test_default_limit_is_50(case: _Case) -> None:
    """spec 0006 D-3(= `GET /agents`): `limit` 기본 50 - 51개면 50개와 `next_cursor`."""
    world, client, path = _setup(case)
    for _ in range(51):
        case.add(world, "queued")

    body = client.get(path).json()

    assert len(body["items"]) == 50
    assert body["next_cursor"] is not None


@pytest.mark.parametrize("case", _CASES, ids=_IDS)
def test_limit_bounds_are_422(case: _Case) -> None:
    """spec 0006 D-3: `limit` 은 1~200. 0 과 201 은 422, 200 은 통과."""
    _world, client, path = _setup(case)

    assert client.get(path, params={"limit": 0}).status_code == 422
    assert client.get(path, params={"limit": 201}).status_code == 422
    assert client.get(path, params={"limit": 200}).status_code == 200


@pytest.mark.parametrize("case", _CASES, ids=_IDS)
def test_cursor_walk_visits_every_row_exactly_once(case: _Case) -> None:
    """spec 0006 R-4: 커서로 이어 읽으면 겹치지도 빠지지도 않고, 끝은 `next_cursor` null."""
    world, client, path = _setup(case)
    added = [case.add(world, "queued") for _ in range(5)]

    pages = _all_pages(client, path, limit=2)

    assert [len(p) for p in pages] == [2, 2, 1]
    seen = [item[case.id_key] for page in pages for item in page]
    assert sorted(seen) == sorted(added)
    assert len(set(seen)) == len(seen)


@pytest.mark.parametrize("case", _FILTERED, ids=lambda c: c.name)
def test_status_filter_keeps_only_that_status_across_pages(case: _Case) -> None:
    """spec 0006 2.3: `status` 필터는 그 상태만 남기고, 필터가 걸려도 커서가 이어진다."""
    assert case.statuses is not None
    first, second = case.statuses
    world, client, path = _setup(case)
    wanted = {case.add(world, second) for _ in range(3)}
    for _ in range(2):
        case.add(world, first)

    pages = _all_pages(client, path, limit=2, status=second)

    seen = [item for page in pages for item in page]
    assert {item[case.id_key] for item in seen} == wanted
    assert len(seen) == 3
    assert {item["status"] for item in seen} == {second}
    assert [len(p) for p in pages] == [2, 1]


@pytest.mark.parametrize("case", _FILTERED, ids=lambda c: c.name)
def test_unknown_status_is_422(case: _Case) -> None:
    """spec 0006 2.3: 모르는 상태 값은 조용히 빈 목록이 아니라 422."""
    _world, client, path = _setup(case)

    assert client.get(path, params={"status": "no-such-status"}).status_code == 422


def test_ingestions_of_unknown_set_is_404() -> None:
    """spec 0006 2.3: 없는 집합의 적재 목록은 404 `knowledge_set_not_found`(POST 와 같은 코드)."""
    client = _World().client()

    response = client.get(f"/knowledge-sets/{uuid4()}/ingestions")

    assert response.status_code == 404
    assert response.json() == {"detail": "knowledge_set_not_found"}


def test_ingestions_list_only_the_requested_set() -> None:
    """spec 0006 2.3: 적재 목록은 그 집합의 것만 - 다른 집합의 적재는 섞이지 않는다."""
    world = _World()
    other = world.knowledge.create_set("other")
    wanted = world.add_ingestion()
    world.knowledge.create_ingestion(other.id, "/b")

    items = world.client().get(f"/knowledge-sets/{world.fixed_set}/ingestions").json()["items"]

    assert [item["ingestion_id"] for item in items] == [wanted]


@pytest.mark.parametrize("case", _CASES, ids=_IDS)
def test_sort_direction_is_fixed_per_path(case: _Case) -> None:
    """spec 0006 2.3: runs·workflow-runs·ingestions 는 최신 것부터, workflows·knowledge-sets 는
    오래된 것부터 - 첫 쪽의 첫 항목이 그 방향의 끝이고, 쪽을 넘겨도 방향이 이어진다."""
    world, client, path = _setup(case)
    added = [case.add(world, "queued") for _ in range(4)]
    expected = list(reversed(added)) if case.newest_first else added

    first_page = client.get(path, params={"limit": 2}).json()["items"]
    walked = [i[case.id_key] for page in _all_pages(client, path, limit=3) for i in page]

    assert first_page[0][case.id_key] == expected[0]
    assert walked == expected


_BAD_CURSORS = ["", "!!not-base64!!", base64.urlsafe_b64encode(b"garbage").decode("ascii")]


@pytest.mark.parametrize("bad", _BAD_CURSORS, ids=["empty", "not-base64", "wrong-format"])
@pytest.mark.parametrize("case", _CASES, ids=_IDS)
def test_malformed_cursor_is_422_not_500(case: _Case, bad: str) -> None:
    """spec 0006 2.3: 깨진 `cursor` 는 클라이언트 입력 오류 - 500 이 아니라 422."""
    _world, client, path = _setup(case)

    response = client.get(path, params={"cursor": bad})

    assert response.status_code == 422, response.text


@pytest.mark.parametrize("bad", _BAD_CURSORS, ids=["empty", "not-base64", "wrong-format"])
def test_agents_malformed_cursor_is_422_not_500(bad: str) -> None:
    """spec 0006 2.3: `GET /agents` 도 같은 입력에 같은 응답(이전엔 500) - 여섯 경로가 한 규칙."""
    app = FastAPI()
    app.include_router(
        build_agents_router(
            _principal,
            CreateAgentUseCase(repo := FakeAgentRepository()),
            ListAgentsUseCase(repo),
            GetAgentUseCase(repo),
            GetAgentVersionUseCase(repo),
            UpdateAgentUseCase(repo),
        )
    )

    assert TestClient(app).get("/agents", params={"cursor": bad}).status_code == 422
