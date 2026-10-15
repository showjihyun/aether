"""spec 0005 2.2, R-1: `DefineWorkflow` — 열한 거부 사유가 각각 다른 사유로 400, 올바른 그래프는
201 이고 Version 1. DB 없음(fake 저장소)."""

from __future__ import annotations

from typing import Any

import pytest
from aether_workflow.domain.validation import Reason

from apps.api.tests.workflow_support import (
    _REJECTIONS,
    AGENT_ID,
    _c,
    _client,
    _e,
    _n,
    _valid_body,
)


def test_rejection_cases_cover_every_reason() -> None:
    """spec 0005 2.2: 사유 값은 열한 개이고 이 파일의 사례가 전부를 덮는다(자기 증명)."""
    assert len(Reason) == 11
    assert set(_REJECTIONS) == set(Reason)


@pytest.mark.parametrize("reason", list(Reason), ids=lambda r: r.value)
def test_post_rejects_each_invalid_graph_with_its_own_reason(reason: Reason) -> None:
    """spec 0005 R-1: 열한 거부가 각각 다른 사유로 400 이다."""
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


def test_agent_reference_round_trips_through_post_and_get() -> None:
    """spec 0005 2.2 개정 3: 노드의 `agent_id`·`agent_version` 을 받고 그대로 돌려준다(선택 키)."""
    client, _ = _client()
    other = "00000000-0000-0000-0000-0000000000b2"
    body = {
        "name": "refs",
        "nodes": [
            _n("s", "START"),
            _n("a", "AGENT", agent_id=other, agent_version=3),
            _n("b", "AGENT"),
            _n("e", "END"),
        ],
        "edges": [_e("s", "a"), _e("a", "b"), _e("b", "e")],
    }

    created = client.post("/workflows", json=body)

    assert created.status_code == 201, created.text
    by_id = {n["id"]: n for n in created.json()["nodes"]}
    assert (by_id["a"]["agent_id"], by_id["a"]["agent_version"]) == (other, 3)
    assert (by_id["b"]["agent_id"], by_id["b"]["agent_version"]) == (AGENT_ID, None)
    assert (by_id["s"]["agent_id"], by_id["s"]["agent_version"]) == (None, None)
    again = client.get(f"/workflows/{created.json()['id']}/versions/1").json()
    assert {n["id"]: (n["agent_id"], n["agent_version"]) for n in again["nodes"]} == {
        "s": (None, None),
        "a": (other, 3),
        "b": (AGENT_ID, None),
        "e": (None, None),
    }


def test_node_without_agent_keys_is_accepted_for_non_agent_kinds() -> None:
    """spec 0005 2.2 개정 3: 두 키는 선택이다 — 기존 호출자의 본문(키 없음)은 그대로 받는다."""
    client, _ = _client()
    body = {
        "name": "legacy",
        "nodes": [{"id": "s", "kind": "START"}, {"id": "e", "kind": "END"}],
        "edges": [_e("s", "e")],
    }

    response = client.post("/workflows", json=body)

    assert response.status_code == 201, response.text
    assert response.json()["nodes"][0]["agent_id"] is None


def test_agent_node_without_agent_names_only_that_node() -> None:
    """spec 0005 2.2 개정 3: 참조 없는 AGENT 는 400 + `agent_node_without_agent`, 그 노드만."""
    client, _ = _client()
    body = {
        "name": "bad",
        "nodes": [
            _n("s", "START"),
            _n("ok", "AGENT"),
            _n("bare", "AGENT", bare=True),
            _n("e", "END"),
        ],
        "edges": [_e("s", "ok"), _e("ok", "bare"), _e("bare", "e")],
    }

    response = client.post("/workflows", json=body)

    assert response.status_code == 400
    assert response.json()["violations"] == [
        {"reason": "agent_node_without_agent", "node_id": "bare"}
    ]


def _condition_body() -> dict[str, Any]:
    return {
        "name": "branching",
        "nodes": [
            _n("s", "START"),
            _c("c", condition_operator="gt", condition_path="input.n", condition_value=3),
            _n("t", "END"),
            _n("f", "END"),
        ],
        "edges": [_e("s", "c"), _e("c", "t", "true"), _e("c", "f", "false")],
    }


def test_condition_keys_round_trip_through_post_and_get() -> None:
    """spec 0005 2.2 개정 4: `condition_path`·`condition_operator`·`condition_value` 를 받고 그대로
    돌려준다. 값의 타입(숫자)이 보존된다."""
    client, _ = _client()

    created = client.post("/workflows", json=_condition_body())

    assert created.status_code == 201, created.text
    wanted = ("input.n", "gt", 3)
    for nodes in (
        created.json()["nodes"],
        client.get(f"/workflows/{created.json()['id']}/versions/1").json()["nodes"],
    ):
        by_id = {n["id"]: n for n in nodes}
        got = (
            by_id["c"]["condition_path"],
            by_id["c"]["condition_operator"],
            by_id["c"]["condition_value"],
        )
        assert got == wanted
        assert by_id["s"]["condition_path"] is None
        assert by_id["s"]["condition_operator"] is None
        assert by_id["s"]["condition_value"] is None


def test_an_operator_outside_the_six_is_refused_by_request_validation() -> None:
    """spec D-9: 연산자는 여섯으로 닫혀 있다 - 임의 표현식을 받지 않는다."""
    client, repo = _client()
    body = _condition_body()
    body["nodes"][1]["condition_operator"] = "matches_regex"

    response = client.post("/workflows", json=body)

    assert response.status_code == 422, response.text
    assert repo._names == {}


def test_node_without_condition_keys_is_accepted_for_every_kind() -> None:
    """기존 호출자의 본문(세 키 없음)은 그대로 받는다."""
    client, _ = _client()
    body = _valid_body()
    assert all("condition_path" not in n for n in body["nodes"])

    assert client.post("/workflows", json=body).status_code == 201
