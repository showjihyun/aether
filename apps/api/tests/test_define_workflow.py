"""spec 0005 2.2, R-1: `DefineWorkflow` — 여덟 거부 사유가 각각 다른 사유로 400, 올바른 그래프는
201 이고 Version 1. DB 없음(fake 저장소)."""

from __future__ import annotations

import pytest
from aether_workflow.domain.validation import Reason

from apps.api.tests.workflow_support import _REJECTIONS, _client, _valid_body


def test_rejection_cases_cover_every_reason() -> None:
    """spec 0005 2.2: 사유 값은 여덟 개이고 이 파일의 사례가 전부를 덮는다(자기 증명)."""
    assert len(Reason) == 8
    assert set(_REJECTIONS) == set(Reason)


@pytest.mark.parametrize("reason", list(Reason), ids=lambda r: r.value)
def test_post_rejects_each_invalid_graph_with_its_own_reason(reason: Reason) -> None:
    """spec 0005 R-1: 여덟 거부가 각각 다른 사유로 400 이다."""
    client, repo = _client()

    response = client.post("/workflows", json={"name": "bad", **_REJECTIONS[reason]})

    assert response.status_code == 400, response.text
    body = response.json()
    assert body["detail"] == "invalid_workflow_graph"
    assert {v["reason"] for v in body["violations"]} == {reason.value}
    assert repo._names == {}, "거부된 정의가 저장되었다"


def test_post_valid_graph_is_201_with_version_one() -> None:
    """spec 0005 R-1: 올바른 그래프는 201 이고 Version 1 이다."""
    client, _ = _client()

    response = client.post("/workflows", json=_valid_body())

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["name"] == "ok"
    assert body["current_version"] == 1
    assert [n["id"] for n in body["nodes"]] == ["s", "a", "e"]
    assert [(e["source"], e["target"]) for e in body["edges"]] == [("s", "a"), ("a", "e")]


def test_violations_name_the_offending_node() -> None:
    """spec 0005 R-1: 위반은 가리키는 노드를 함께 돌려준다."""
    client, _ = _client()

    response = client.post("/workflows", json={"name": "bad", **_REJECTIONS[Reason.ORPHAN_NODE]})

    assert response.json()["violations"] == [{"reason": "orphan_node", "node_id": "lonely"}]
