"""spec 0005 R-1, R-2, D-12: `UpdateWorkflow` — PUT 은 새 Version 을 만들고 기존 Version 은 그대로,
거부된 PUT 은 400 이며 새 Version 이 없다, 없는 Workflow 는 404. DB 없음(fake 저장소)."""

from __future__ import annotations

from uuid import uuid4

import pytest
from aether_workflow.domain.validation import Reason

from apps.api.tests.workflow_support import _REJECTIONS, _client, _e, _n, _valid_body


def test_put_creates_new_version_and_keeps_the_old_one() -> None:
    """spec 0005 R-2, D-12: PUT 은 새 Version 을 만들고 Version 1 은 그대로다."""
    client, _ = _client()
    created = client.post("/workflows", json=_valid_body()).json()
    workflow_id = created["id"]
    v2_body = {
        "nodes": [_n("s", "START"), _n("b", "AGENT"), _n("e", "END")],
        "edges": [_e("s", "b"), _e("b", "e")],
    }

    put = client.put(f"/workflows/{workflow_id}", json=v2_body)

    assert put.status_code == 200, put.text
    assert put.json()["current_version"] == 2
    v1 = client.get(f"/workflows/{workflow_id}/versions/1").json()
    assert [n["id"] for n in v1["nodes"]] == ["s", "a", "e"]
    v2 = client.get(f"/workflows/{workflow_id}/versions/2").json()
    assert [n["id"] for n in v2["nodes"]] == ["s", "b", "e"]
    assert client.get(f"/workflows/{workflow_id}").json()["current_version"] == 2


@pytest.mark.parametrize("reason", list(Reason), ids=lambda r: r.value)
def test_put_rejects_each_invalid_graph_and_creates_no_version(reason: Reason) -> None:
    """spec 0005 R-1, D-12: 거부된 PUT 은 400 이고 새 Version 을 만들지 않는다."""
    client, _ = _client()
    workflow_id = client.post("/workflows", json=_valid_body()).json()["id"]

    response = client.put(f"/workflows/{workflow_id}", json=_REJECTIONS[reason])

    assert response.status_code == 400, response.text
    assert {v["reason"] for v in response.json()["violations"]} == {reason.value}
    assert client.get(f"/workflows/{workflow_id}").json()["current_version"] == 1
    assert client.get(f"/workflows/{workflow_id}/versions/2").status_code == 404


def test_put_unknown_workflow_is_404_with_code() -> None:
    """오류 응답 모양은 {"detail": "<코드>"}."""
    client, _ = _client()

    assert client.put(f"/workflows/{uuid4()}", json=_valid_body()).json() == {
        "detail": "workflow_not_found"
    }
