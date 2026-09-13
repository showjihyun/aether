"""spec 0002 2.2: `ListAgentsUseCase` — 커서 페이지가 이어집니다.

`FakeAgentRepository` 의 커서는 정렬된 목록의 정수 오프셋을 감싼 불투명 문자열입니다.
"""

from __future__ import annotations

from typing import Any

from aether_api.application.usecases.create_agent import CreateAgentUseCase
from aether_api.application.usecases.list_agents import ListAgentsUseCase
from aether_runtime.domain.agent import AgentDefinition

from apps.api.tests.fakes import FakeAgentRepository


def _definition(**overrides: Any) -> AgentDefinition:
    payload: dict[str, Any] = {"schema_version": 1, "system_prompt": "You are a helper."}
    payload.update(overrides)
    return AgentDefinition.model_validate(payload)


def test_list_agents_pages_with_cursor() -> None:
    """spec 0002 2.2: `limit` 보다 많은 Agent 가 있으면 `next_cursor` 로 다음 페이지가 이어집니다.

    (page1 == limit, next_cursor != None) -> (page2 로 나머지, next_cursor == None)
    """
    repo = FakeAgentRepository()
    create_agent = CreateAgentUseCase(repo)
    list_agents = ListAgentsUseCase(repo)
    create_agent("a", _definition())
    create_agent("b", _definition())
    create_agent("c", _definition())

    page1 = list_agents(2, None)
    assert len(page1.items) == 2
    assert page1.next_cursor is not None

    page2 = list_agents(2, page1.next_cursor)
    assert len(page2.items) == 1
    assert page2.next_cursor is None

    names = {agent.name for agent in page1.items} | {agent.name for agent in page2.items}
    assert names == {"a", "b", "c"}


def test_list_agents_empty_repository_returns_empty_page() -> None:
    """spec 0002 2.2: Agent 가 없으면 빈 목록과 `next_cursor is None`."""
    repo = FakeAgentRepository()
    list_agents = ListAgentsUseCase(repo)

    page = list_agents(50, None)

    assert page.items == []
    assert page.next_cursor is None
