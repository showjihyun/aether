"""spec 0004 2.4, D-4: Knowledge 적재 선언 HTTP 계약 — 실제 PostgreSQL + Redis + 실제 인증.

`api-integration`. `POST /knowledge-sets` 201 → `POST /knowledge-sets/{id}/ingestions`
202(필드 전부, `status == "queued"`) → `requested` 스트림 메시지 → `GET /knowledge-
ingestions/{id}` 투영. 알 수 없는 집합은 `404`.
"""

from __future__ import annotations

from collections.abc import Callable
from uuid import uuid4

import psycopg
import pytest
from aether_api.adapters.outbound.db.api_keys import PostgresApiKeyStore
from aether_api.application.usecases.issue_api_key import IssueApiKeyUseCase
from aether_api.main import create_app
from aether_api.settings import Settings
from fastapi.testclient import TestClient
from redis import Redis

pytestmark = pytest.mark.integration

_STREAM = "aether:knowledge:ingestions:requested"


@pytest.fixture
def client(control_database_url: str, redis_url: str) -> TestClient:
    settings = Settings(database_url=control_database_url, redis_url=redis_url)
    app = create_app(settings)
    return TestClient(app)


@pytest.fixture
def auth_headers(control_connection_factory: Callable[[], psycopg.Connection]) -> dict[str, str]:
    store = PostgresApiKeyStore(control_connection_factory)
    issued = IssueApiKeyUseCase(store)(f"test-knowledge-api-{uuid4()}")
    return {"Authorization": f"Bearer {issued.raw_key}"}


def test_create_set_request_ingestion_and_get_detail(
    client: TestClient, auth_headers: dict[str, str], redis_client: Redis
) -> None:
    create_response = client.post(
        "/knowledge-sets", json={"name": f"docs-{uuid4()}"}, headers=auth_headers
    )
    assert create_response.status_code == 201
    knowledge_set_id = create_response.json()["id"]

    ingest_response = client.post(
        f"/knowledge-sets/{knowledge_set_id}/ingestions",
        json={"source": "/srv/docs"},
        headers=auth_headers,
    )
    assert ingest_response.status_code == 202
    body = ingest_response.json()
    assert body["knowledge_set_id"] == knowledge_set_id
    assert body["source"] == "/srv/docs"
    assert body["status"] == "queued"
    ingestion_id = body["ingestion_id"]

    entries = redis_client.xrange(_STREAM, min="-", max="+")
    assert entries is not None
    matched: list[dict[str, str]] = []
    for _entry_id, raw_fields in entries:
        assert raw_fields is not None
        fields = {str(key): str(value) for key, value in raw_fields.items()}
        if fields.get("ingestion_id") == ingestion_id:
            matched.append(fields)
    assert len(matched) == 1
    assert matched[0]["knowledge_set_id"] == knowledge_set_id
    assert matched[0]["source"] == "/srv/docs"

    detail_response = client.get(f"/knowledge-ingestions/{ingestion_id}", headers=auth_headers)
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["status"] == "queued"
    assert detail["started_at"] is None
    assert detail["finished_at"] is None


def test_request_ingestion_for_unknown_set_is_404(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    response = client.post(
        f"/knowledge-sets/{uuid4()}/ingestions",
        json={"source": "/srv/docs"},
        headers=auth_headers,
    )
    assert response.status_code == 404
    assert response.json() == {"detail": "knowledge_set_not_found"}


def test_get_unknown_ingestion_is_404(client: TestClient, auth_headers: dict[str, str]) -> None:
    response = client.get(f"/knowledge-ingestions/{uuid4()}", headers=auth_headers)
    assert response.status_code == 404
    assert response.json() == {"detail": "knowledge_ingestion_not_found"}
