"""spec 0002 2.2, D-9, D-11 (P1-5b): Run API — 실제 PostgreSQL + Redis + 실제 인증.

`api-integration`. `POST /agents/{id}/run` 202 필드 전부·`requested_by == 키 id`·
`control.runs` 행·`requested` 스트림 메시지(`run_id`, `agent_version_id`,
`traceparent` 필드 존재). `agent_version` 지정·미지정. `GET` 은 `queued`(투영
소비자가 이 테스트에서는 돌지 않으므로 — `TestClient(app)` 를 `with` 없이 씁니다).
`cancel` 멱등(두 번 같은 `cancel_requested_at`)·종결 뒤도 202. `404` 셋.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any
from uuid import uuid4

import psycopg
import pytest
from aether_api.adapters.outbound.db.api_keys import PostgresApiKeyStore
from aether_api.application.ports.inbound.issue_api_key import IssuedApiKey
from aether_api.application.usecases.issue_api_key import IssueApiKeyUseCase
from aether_api.main import create_app
from aether_api.settings import Settings
from fastapi.testclient import TestClient
from redis import Redis

pytestmark = pytest.mark.integration

_STREAM = "aether:runs:requested"


def _definition_payload(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {"schema_version": 1, "system_prompt": "You are a helper."}
    payload.update(overrides)
    return payload


def _xrange_all(client: Redis, stream: str) -> list[tuple[str, dict[str, str]]]:
    """redis-py 스텁이 `None`/`bytes` 를 허용하는 반환 타입을 좁힙니다(`decode_responses=True`
    로 접속했으므로 런타임에는 항상 `str` — `test_run_notifier.py` 와 같은 헬퍼)."""
    entries = client.xrange(stream, min="-", max="+")
    assert entries is not None
    result: list[tuple[str, dict[str, str]]] = []
    for entry_id, fields in entries:
        assert isinstance(entry_id, str)
        assert fields is not None
        narrowed: dict[str, str] = {}
        for key, value in fields.items():
            assert isinstance(key, str)
            assert isinstance(value, str)
            narrowed[key] = value
        result.append((entry_id, narrowed))
    return result


@pytest.fixture
def client(control_database_url: str, redis_url: str) -> TestClient:
    settings = Settings(database_url=control_database_url, redis_url=redis_url)
    app = create_app(settings)
    return TestClient(app)


@pytest.fixture
def issued_key(control_connection_factory: Callable[[], psycopg.Connection]) -> IssuedApiKey:
    store = PostgresApiKeyStore(control_connection_factory)
    return IssueApiKeyUseCase(store)(f"test-runs-api-{uuid4()}")


@pytest.fixture
def auth_headers(issued_key: IssuedApiKey) -> dict[str, str]:
    return {"Authorization": f"Bearer {issued_key.raw_key}"}


def _create_agent(client: TestClient, headers: dict[str, str]) -> str:
    response = client.post(
        "/agents",
        json={"name": f"run-agent-{uuid4()}", "definition": _definition_payload()},
        headers=headers,
    )
    assert response.status_code == 201, response.text
    agent_id: str = response.json()["id"]
    return agent_id


def test_post_run_returns_202_with_full_fields(
    client: TestClient, auth_headers: dict[str, str], issued_key: IssuedApiKey
) -> None:
    agent_id = _create_agent(client, auth_headers)

    response = client.post(f"/agents/{agent_id}/run", json={"input": "do it"}, headers=auth_headers)

    assert response.status_code == 202, response.text
    body = response.json()
    assert set(body.keys()) == {
        "run_id",
        "agent_id",
        "agent_version",
        "status",
        "requested_at",
        "requested_by",
    }
    assert body["agent_id"] == agent_id
    assert body["agent_version"] == 1
    assert body["status"] == "queued"
    assert body["requested_by"] == str(issued_key.key.id)


def test_post_run_persists_the_declaration_in_control_runs(
    client: TestClient,
    auth_headers: dict[str, str],
    control_connection_factory: Callable[[], psycopg.Connection],
) -> None:
    agent_id = _create_agent(client, auth_headers)

    response = client.post(f"/agents/{agent_id}/run", json={"input": "do it"}, headers=auth_headers)
    run_id = response.json()["run_id"]

    with control_connection_factory() as conn, conn.cursor() as cur:
        cur.execute("SELECT input, status FROM control.runs WHERE id = %s", (run_id,))
        row = cur.fetchone()
    assert row is not None
    assert row[0] == "do it"
    assert row[1] == "queued"


def test_post_run_sends_a_requested_message_with_traceparent_field(
    client: TestClient, auth_headers: dict[str, str], redis_client: Redis
) -> None:
    agent_id = _create_agent(client, auth_headers)

    response = client.post(f"/agents/{agent_id}/run", json={"input": "do it"}, headers=auth_headers)
    body = response.json()

    entries = _xrange_all(redis_client, _STREAM)
    assert len(entries) == 1
    _message_id, fields = entries[0]
    assert fields["run_id"] == body["run_id"]
    assert fields["agent_version_id"]  # 존재 — 실제 값은 test_run_notifier.py 가 검증
    assert "traceparent" in fields


def test_post_run_without_agent_version_uses_current_version(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    agent_id = _create_agent(client, auth_headers)
    client.put(
        f"/agents/{agent_id}",
        json={"definition": _definition_payload(system_prompt="v2")},
        headers=auth_headers,
    )

    response = client.post(f"/agents/{agent_id}/run", json={"input": "do it"}, headers=auth_headers)

    assert response.status_code == 202, response.text
    assert response.json()["agent_version"] == 2


def test_post_run_with_explicit_agent_version(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    agent_id = _create_agent(client, auth_headers)
    client.put(
        f"/agents/{agent_id}",
        json={"definition": _definition_payload(system_prompt="v2")},
        headers=auth_headers,
    )

    response = client.post(
        f"/agents/{agent_id}/run",
        json={"input": "do it", "agent_version": 1},
        headers=auth_headers,
    )

    assert response.status_code == 202, response.text
    assert response.json()["agent_version"] == 1


def test_post_run_unknown_agent_is_404(client: TestClient, auth_headers: dict[str, str]) -> None:
    response = client.post(f"/agents/{uuid4()}/run", json={"input": "do it"}, headers=auth_headers)

    assert response.status_code == 404
    assert response.json() == {"detail": "agent_not_found"}


def test_post_run_unknown_agent_version_is_404(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    agent_id = _create_agent(client, auth_headers)

    response = client.post(
        f"/agents/{agent_id}/run",
        json={"input": "do it", "agent_version": 7},
        headers=auth_headers,
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "agent_version_not_found"}


def test_get_run_returns_queued_right_after_post(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    """투영 소비자가 이 테스트에서는 돌지 않습니다(`with` 없는 `TestClient`) — 항상
    `queued` 입니다(spec 2.2 — "투영이 아직 도착하지 않았으면 queued")."""
    agent_id = _create_agent(client, auth_headers)
    run_id = client.post(
        f"/agents/{agent_id}/run", json={"input": "do it"}, headers=auth_headers
    ).json()["run_id"]

    response = client.get(f"/runs/{run_id}", headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) == {
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
    assert body["status"] == "queued"
    assert body["started_at"] is None
    assert body["cancel_requested_at"] is None


def test_get_run_missing_is_404(client: TestClient, auth_headers: dict[str, str]) -> None:
    response = client.get(f"/runs/{uuid4()}", headers=auth_headers)

    assert response.status_code == 404
    assert response.json() == {"detail": "run_not_found"}


def test_cancel_is_idempotent_and_keeps_the_first_timestamp(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    agent_id = _create_agent(client, auth_headers)
    run_id = client.post(
        f"/agents/{agent_id}/run", json={"input": "do it"}, headers=auth_headers
    ).json()["run_id"]

    first = client.post(f"/runs/{run_id}/cancel", headers=auth_headers)
    second = client.post(f"/runs/{run_id}/cancel", headers=auth_headers)

    assert first.status_code == 202, first.text
    assert second.status_code == 202, second.text
    first_body = first.json()
    second_body = second.json()
    assert first_body["run_id"] == run_id
    assert first_body["cancel_requested_at"] is not None
    assert second_body["cancel_requested_at"] == first_body["cancel_requested_at"]


def test_cancel_on_terminal_run_still_returns_202_with_current_status(
    client: TestClient,
    auth_headers: dict[str, str],
    control_connection_factory: Callable[[], psycopg.Connection],
) -> None:
    agent_id = _create_agent(client, auth_headers)
    run_id = client.post(
        f"/agents/{agent_id}/run", json={"input": "do it"}, headers=auth_headers
    ).json()["run_id"]

    with control_connection_factory() as conn, conn.cursor() as cur:
        cur.execute(
            "UPDATE control.runs SET status = 'succeeded', status_seq = 1 WHERE id = %s",
            (run_id,),
        )

    response = client.post(f"/runs/{run_id}/cancel", headers=auth_headers)

    assert response.status_code == 202, response.text
    assert response.json()["status"] == "succeeded"


def test_cancel_missing_run_is_404(client: TestClient, auth_headers: dict[str, str]) -> None:
    response = client.post(f"/runs/{uuid4()}/cancel", headers=auth_headers)

    assert response.status_code == 404
    assert response.json() == {"detail": "run_not_found"}
