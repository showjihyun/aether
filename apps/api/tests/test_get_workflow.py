"""spec 0005 2.2: `GetWorkflow` — 없는 Workflow 는 404 `workflow_not_found`. DB 없음."""

from __future__ import annotations

from uuid import uuid4

from apps.api.tests.workflow_support import _client


def test_get_unknown_workflow_is_404_with_code() -> None:
    """오류 응답 모양은 {"detail": "<코드>"}."""
    client, _ = _client()

    assert client.get(f"/workflows/{uuid4()}").json() == {"detail": "workflow_not_found"}
