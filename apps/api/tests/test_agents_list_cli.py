"""`aether-api agents list --limit --cursor --name` 서브커맨드.

spec 0002 2.2 R-1 과 같은 이유로 `test_agent_version_cli.py` 를 따릅니다: `ListAgents`
는 이미 HTTP 라우터에 붙어 있는 inbound 포트입니다(`test_list_agents.py` 가 유스케이스를,
`test_agents_api.py` 가 HTTP 어댑터를 검사합니다). 이 파일은 같은 포트의 두 번째 inbound
어댑터인 CLI 함수만 봅니다(AR-12) — `FakeAgentRepository` 로 만든 `ListAgentsUseCase` 를
그대로 꽂아, 컨테이너 없이 "커서 페이지가 JSON 한 문서로 stdout 에 나간다" 를 증명합니다.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from aether_api.adapters.inbound.cli import agents_list, build_parser
from aether_api.application.usecases.create_agent import CreateAgentUseCase
from aether_api.application.usecases.list_agents import ListAgentsUseCase
from aether_runtime.domain.agent import AgentDefinition

from apps.api.tests.fakes import FakeAgentRepository


def _ticking_clock() -> Any:
    """호출마다 1 초씩 늘어나는 시계 — `FakeAgentRepository.list` 의 정렬 순서를 고정합니다."""
    start = datetime(2026, 1, 1, tzinfo=UTC)
    counter = {"n": 0}

    def clock() -> datetime:
        counter["n"] += 1
        return start + timedelta(seconds=counter["n"])

    return clock


def _definition(**overrides: Any) -> AgentDefinition:
    payload: dict[str, Any] = {"schema_version": 1, "system_prompt": "You are a helper."}
    payload.update(overrides)
    return AgentDefinition.model_validate(payload)


def test_build_parser_accepts_agents_list_with_no_args() -> None:
    parser = build_parser()

    args = parser.parse_args(["agents", "list"])

    assert args.command == "agents"
    assert args.agents_command == "list"
    assert args.limit == 50
    assert args.cursor is None
    assert args.name is None


def test_build_parser_accepts_agents_list_with_all_options() -> None:
    parser = build_parser()

    args = parser.parse_args(
        ["agents", "list", "--limit", "10", "--cursor", "5", "--name", "billing"]
    )

    assert args.limit == 10
    assert args.cursor == "5"
    assert args.name == "billing"


def test_agents_list_prints_items_and_next_cursor_as_json(
    capsys: pytest.CaptureFixture[str],
) -> None:
    repo = FakeAgentRepository(clock=_ticking_clock())
    create_agent = CreateAgentUseCase(repo)
    list_agents = ListAgentsUseCase(repo)
    agent_a = create_agent("a", _definition())
    create_agent("b", _definition())

    agents_list(list_agents, 1, None, None)

    captured = capsys.readouterr()
    printed = json.loads(captured.out)
    assert printed["next_cursor"] == "1"
    assert printed["items"] == [
        {
            "id": str(agent_a.id),
            "name": "a",
            "current_version": 1,
            "updated_at": agent_a.updated_at.isoformat(),
        }
    ]


def test_agents_list_filters_by_name_substring_case_insensitive(
    capsys: pytest.CaptureFixture[str],
) -> None:
    repo = FakeAgentRepository()
    create_agent = CreateAgentUseCase(repo)
    list_agents = ListAgentsUseCase(repo)
    create_agent("billing-agent", _definition())
    create_agent("support-agent", _definition())

    agents_list(list_agents, 50, None, "BILLING")

    captured = capsys.readouterr()
    printed = json.loads(captured.out)
    assert [item["name"] for item in printed["items"]] == ["billing-agent"]


def test_agents_list_empty_repository_prints_empty_items_and_null_cursor(
    capsys: pytest.CaptureFixture[str],
) -> None:
    repo = FakeAgentRepository()
    list_agents = ListAgentsUseCase(repo)

    agents_list(list_agents, 50, None, None)

    captured = capsys.readouterr()
    printed = json.loads(captured.out)
    assert printed == {"items": [], "next_cursor": None}
