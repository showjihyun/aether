"""spec 0002 R-1, R-12, 2.2 D-9: Agent Registry API — 실제 PostgreSQL + 실제 인증.

`api-integration`. `IssueApiKeyUseCase(PostgresApiKeyStore(...))` 로 발급한 진짜 키를
`Authorization: Bearer` 로 씁니다(P0-9). 생성 → 조회 → 수정 → 버전 조회, 커서 페이지,
`409`, `404` 둘, `422` 둘을 API 로만 판정합니다(R-1: "API 로만 판정").
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any
from uuid import uuid4

import psycopg
import pytest
from aether_api.adapters.outbound.db.api_keys import PostgresApiKeyStore
from aether_api.application.usecases.issue_api_key import IssueApiKeyUseCase
from aether_api.main import create_app
from aether_api.settings import Settings
from fastapi.testclient import TestClient

pytestmark = pytest.mark.integration


def _definition_payload(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {"schema_version": 1, "system_prompt": "You are a helper."}
    payload.update(overrides)
    return payload


@pytest.fixture
def client(control_database_url: str) -> TestClient:
    settings = Settings(database_url=control_database_url)
    app = create_app(settings)
    return TestClient(app)


@pytest.fixture
def auth_headers(control_connection_factory: Callable[[], psycopg.Connection]) -> dict[str, str]:
    store = PostgresApiKeyStore(control_connection_factory)
    issued = IssueApiKeyUseCase(store)(f"test-agents-api-{uuid4()}")
    return {"Authorization": f"Bearer {issued.raw_key}"}


def test_create_get_update_and_version_history(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    """spec 0002 R-1: 생성 → 조회 → 수정(current_version==2) → versions/1 의 definition 동일."""
    name = f"weather-bot-{uuid4()}"
    create_response = client.post(
        "/agents",
        json={"name": name, "definition": _definition_payload(system_prompt="v1 prompt")},
        headers=auth_headers,
    )
    assert create_response.status_code == 201, create_response.text
    created = create_response.json()
    assert created["name"] == name
    assert created["current_version"] == 1
    assert set(created.keys()) == {"id", "name", "current_version", "created_at", "updated_at"}
    agent_id = created["id"]

    get_response = client.get(f"/agents/{agent_id}", headers=auth_headers)
    assert get_response.status_code == 200
    detail = get_response.json()
    assert detail["current_version"] == 1
    assert detail["definition"]["system_prompt"] == "v1 prompt"
    assert [v["version"] for v in detail["versions"]] == [1]
    assert set(detail["versions"][0].keys()) == {"version", "created_at"}

    put_response = client.put(
        f"/agents/{agent_id}",
        json={"definition": _definition_payload(system_prompt="v2 prompt")},
        headers=auth_headers,
    )
    assert put_response.status_code == 200, put_response.text
    updated = put_response.json()
    assert updated["current_version"] == 2
    assert updated["name"] == name
    assert updated["definition"]["system_prompt"] == "v2 prompt"
    assert [v["version"] for v in updated["versions"]] == [1, 2]

    version_1_response = client.get(f"/agents/{agent_id}/versions/1", headers=auth_headers)
    assert version_1_response.status_code == 200
    version_1 = version_1_response.json()
    assert version_1["definition"]["system_prompt"] == "v1 prompt"
    assert version_1["agent_id"] == agent_id
    assert version_1["version"] == 1


def test_list_agents_pages_with_cursor(client: TestClient, auth_headers: dict[str, str]) -> None:
    """spec 0002 2.2: `limit=1` 로 두 페이지가 이어집니다."""
    prefix = f"cursor-{uuid4()}"
    first = client.post(
        "/agents",
        json={"name": f"{prefix}-1", "definition": _definition_payload()},
        headers=auth_headers,
    )
    second = client.post(
        "/agents",
        json={"name": f"{prefix}-2", "definition": _definition_payload()},
        headers=auth_headers,
    )
    assert first.status_code == 201
    assert second.status_code == 201

    page1 = client.get("/agents", params={"limit": 1}, headers=auth_headers)
    assert page1.status_code == 200
    page1_body = page1.json()
    assert len(page1_body["items"]) == 1
    assert page1_body["next_cursor"] is not None

    page2 = client.get(
        "/agents",
        params={"limit": 200, "cursor": page1_body["next_cursor"]},
        headers=auth_headers,
    )
    assert page2.status_code == 200
    page2_body = page2.json()
    assert len(page2_body["items"]) >= 1
    seen_ids = {item["id"] for item in page1_body["items"]} | {
        item["id"] for item in page2_body["items"]
    }
    assert first.json()["id"] in seen_ids
    assert second.json()["id"] in seen_ids


def test_list_agents_filters_by_name_substring(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    """`?name=` 은 대소문자 구분 없이 부분 일치하는 Agent 만 돌려줍니다."""
    prefix = uuid4().hex
    matching = client.post(
        "/agents",
        json={"name": f"{prefix}-billing-agent", "definition": _definition_payload()},
        headers=auth_headers,
    )
    other = client.post(
        "/agents",
        json={"name": f"{prefix}-support-agent", "definition": _definition_payload()},
        headers=auth_headers,
    )
    assert matching.status_code == 201
    assert other.status_code == 201

    response = client.get(
        "/agents",
        params={"name": f"{prefix.upper()}-BILLING"},
        headers=auth_headers,
    )

    assert response.status_code == 200
    body = response.json()
    names = {item["name"] for item in body["items"]}
    assert names == {f"{prefix}-billing-agent"}


def test_list_agents_name_filter_with_no_match_is_empty(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    response = client.get(
        "/agents",
        params={"name": f"no-such-agent-{uuid4()}"},
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert response.json()["items"] == []


def test_create_duplicate_name_is_409(client: TestClient, auth_headers: dict[str, str]) -> None:
    name = f"dup-{uuid4()}"
    first = client.post(
        "/agents",
        json={"name": name, "definition": _definition_payload()},
        headers=auth_headers,
    )
    assert first.status_code == 201

    second = client.post(
        "/agents",
        json={"name": name, "definition": _definition_payload()},
        headers=auth_headers,
    )
    assert second.status_code == 409
    assert second.json() == {"detail": "agent_name_taken"}


def test_get_missing_agent_is_404(client: TestClient, auth_headers: dict[str, str]) -> None:
    response = client.get(f"/agents/{uuid4()}", headers=auth_headers)
    assert response.status_code == 404
    assert response.json() == {"detail": "agent_not_found"}


def test_get_missing_version_is_404(client: TestClient, auth_headers: dict[str, str]) -> None:
    create_response = client.post(
        "/agents",
        json={"name": f"solo-{uuid4()}", "definition": _definition_payload()},
        headers=auth_headers,
    )
    agent_id = create_response.json()["id"]

    response = client.get(f"/agents/{agent_id}/versions/2", headers=auth_headers)

    assert response.status_code == 404
    assert response.json() == {"detail": "agent_version_not_found"}


def test_create_with_unknown_tool_is_422(client: TestClient, auth_headers: dict[str, str]) -> None:
    """spec 0002 2.3: `tools` 는 `BUILTIN_TOOL_NAMES` 밖이면 422."""
    response = client.post(
        "/agents",
        json={
            "name": f"bad-tool-{uuid4()}",
            "definition": _definition_payload(tools=["not-a-real-tool"]),
        },
        headers=auth_headers,
    )
    assert response.status_code == 422
    assert isinstance(response.json()["detail"], list)


def test_create_with_wrong_schema_version_is_422(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    """spec 0002 2.3: `schema_version` 은 `Literal[1]` — 다른 값은 422."""
    response = client.post(
        "/agents",
        json={
            "name": f"bad-schema-{uuid4()}",
            "definition": _definition_payload(schema_version=2),
        },
        headers=auth_headers,
    )
    assert response.status_code == 422
    assert isinstance(response.json()["detail"], list)
