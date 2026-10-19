"""spec 0006 R-10, 2.11 (MVP-4): `scenario_offline` 의 순수 함수 계약.

`knowledge_agent_body` 의 docstring 이 적은 함정이 그대로 적용됩니다 - 바인딩이 하나라도
빠지면 시나리오는 성공하지만 아무것도 확인하지 않은 상태가 됩니다. 그래서 컨테이너 없이
정의의 모양을 여기서 고정합니다. HTTP 왕복은 `e2e` 전량 실행만이 판정합니다.
"""

from __future__ import annotations

from typing import Any

import pytest

from scripts import smoke_client
from scripts.smoke_client import offline_agent_body, offline_workflow_body, wait_for_workflow_run


def test_offline_agent_declares_mcp_tool_and_knowledge() -> None:
    """R-10: MCP 서버·도구·knowledge 바인딩이 전부 있다(하나라도 빠지면 빈 성공)."""
    definition = offline_agent_body("docs-x")["definition"]

    assert definition["tools"] == ["read_text_file"]
    assert definition["mcp_servers"] == [
        {"name": "filesystem", "transport": "stdio", "ref": "filesystem"}
    ]
    assert definition["knowledge"] == ["docs-x"]
    assert definition["knowledge_top_k"] > 0
    assert not definition.get("memory_enabled")


def test_offline_workflow_is_start_agent_end_with_agent_pinned() -> None:
    """R-10, spec 0005 R-1: AGENT 노드는 agent_id·agent_version 을 들고 있어야 한다."""
    body = offline_workflow_body("wf-x", "aid", 3)

    nodes = body["nodes"]
    assert body["name"] == "wf-x"
    assert [n["kind"] for n in nodes].count("START") == 1
    agent = next(n for n in nodes if n["kind"] == "AGENT")
    assert agent["agent_id"] == "aid" and agent["agent_version"] == 3
    by_kind = {n["kind"]: n["id"] for n in nodes}
    edges = {(e["source"], e["target"]) for e in body["edges"]}
    assert edges == {(by_kind["START"], by_kind["AGENT"]), (by_kind["AGENT"], by_kind["END"])}


def _stub_get(monkeypatch: pytest.MonkeyPatch, statuses: list[dict[str, Any]]) -> list[int]:
    calls: list[int] = []

    def fake_request(url: str, method: str, key: str, body: Any) -> dict[str, Any]:
        calls.append(1)
        return statuses[min(len(calls), len(statuses)) - 1]

    monkeypatch.setattr(smoke_client, "_request", fake_request)
    monkeypatch.setattr(smoke_client, "SCENARIO_POLL_INTERVAL_SECONDS", 0.0)
    return calls


@pytest.mark.parametrize("terminal", ["failed", "cancelled"])
def test_workflow_wait_raises_immediately_on_failure(
    monkeypatch: pytest.MonkeyPatch, terminal: str
) -> None:
    """R-10: 실패로 끝난 상태는 타임아웃을 기다리지 않고 failure_reason 과 함께 올린다."""
    calls = _stub_get(monkeypatch, [{"status": terminal, "failure_reason": "boom"}])

    with pytest.raises(RuntimeError, match="boom"):
        wait_for_workflow_run("k", "id", 30.0)
    assert len(calls) == 1


def test_workflow_wait_keeps_polling_through_waiting_states(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """R-10: queued/running/waiting_* 는 계속 폴링하고 succeeded 에서 돌려준다."""
    seq = [{"status": s} for s in ("queued", "running", "waiting_run", "waiting_approval")]
    seq += [{"status": "waiting_timer"}, {"status": "succeeded"}]
    calls = _stub_get(monkeypatch, seq)

    assert wait_for_workflow_run("k", "id", 30.0)["status"] == "succeeded"
    assert len(calls) == 6


def test_workflow_wait_times_out(monkeypatch: pytest.MonkeyPatch) -> None:
    """R-10: 끝나지 않으면 TimeoutError."""
    _stub_get(monkeypatch, [{"status": "running"}])

    with pytest.raises(TimeoutError):
        wait_for_workflow_run("k", "id", 0.01)
