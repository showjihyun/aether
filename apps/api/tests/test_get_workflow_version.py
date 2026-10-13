"""spec 0005 2.2, D-12: `GetWorkflowVersion` — 없는 Version 은 404 `workflow_version_not_found`.
DB 없음(fake 저장소)."""

from __future__ import annotations

from apps.api.tests.workflow_support import _client, _valid_body


def test_get_unknown_version_is_404_with_code() -> None:
    """오류 응답 모양은 {"detail": "<코드>"}."""
    client, _ = _client()
    workflow_id = client.post("/workflows", json=_valid_body()).json()["id"]

    assert client.get(f"/workflows/{workflow_id}/versions/9").json() == {
        "detail": "workflow_version_not_found"
    }
