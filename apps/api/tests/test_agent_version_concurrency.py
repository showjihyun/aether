"""spec 0002 2.2 D-9: 동시 `PUT /agents/{id}` — `SELECT … FOR UPDATE` 로 직렬화됩니다.

같은 Agent 에 스레드 8개가 동시에 `PUT` 을 보냅니다. 응답은 전부 200 또는 409(unique
위반은 잠금 밖 경로에서만 나므로 0건이어야 합니다), 최종 `current_version` 은
`1 + 성공(200) 횟수` 와 같고 `agent_versions` 행 수도 그와 같습니다.
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from typing import Any

import psycopg
import pytest
from aether_api.adapters.outbound.db.api_keys import PostgresApiKeyStore
from aether_api.application.usecases.issue_api_key import IssueApiKeyUseCase
from aether_api.main import create_app
from aether_api.settings import Settings
from fastapi.testclient import TestClient

pytestmark = pytest.mark.integration


def _definition_payload(system_prompt: str) -> dict[str, Any]:
    return {"schema_version": 1, "system_prompt": system_prompt}


def test_concurrent_put_serializes_without_500_or_unique_violations(
    control_database_url: str,
    control_connection_factory: Callable[[], psycopg.Connection],
) -> None:
    settings = Settings(database_url=control_database_url)
    app = create_app(settings)
    client = TestClient(app)

    store = PostgresApiKeyStore(control_connection_factory)
    issued = IssueApiKeyUseCase(store)("concurrency-test")
    headers = {"Authorization": f"Bearer {issued.raw_key}"}

    created = client.post(
        "/agents",
        json={
            "name": f"concurrent-{issued.key.id}",
            "definition": _definition_payload("base"),
        },
        headers=headers,
    )
    assert created.status_code == 201, created.text
    agent_id = created.json()["id"]

    thread_count = 8
    results: list[int] = [0] * thread_count

    def _put(index: int) -> None:
        response = client.put(
            f"/agents/{agent_id}",
            json={"definition": _definition_payload(f"update-{index}")},
            headers=headers,
        )
        results[index] = response.status_code

    threads = [threading.Thread(target=_put, args=(i,)) for i in range(thread_count)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert all(status in (200, 409) for status in results), results
    success_count = sum(1 for status in results if status == 200)
    assert success_count >= 1

    final = client.get(f"/agents/{agent_id}", headers=headers)
    assert final.status_code == 200
    assert final.json()["current_version"] == 1 + success_count

    admin_conn = control_connection_factory()
    try:
        with admin_conn.cursor() as cur:
            cur.execute(
                "SELECT count(*) FROM control.agent_versions WHERE agent_id = %s",
                (agent_id,),
            )
            row = cur.fetchone()
    finally:
        admin_conn.close()

    assert row is not None
    assert row[0] == 1 + success_count
