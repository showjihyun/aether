"""spec 0002 2.2: `GetAgentUseCase` — `definition`(현재 버전)과 `versions[]` 를 함께 돌려줍니다."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

import pytest
from aether_api.application.usecases.create_agent import CreateAgentUseCase
from aether_api.application.usecases.get_agent import GetAgentUseCase
from aether_api.application.usecases.update_agent import UpdateAgentUseCase
from aether_api.domain.agent import AgentNotFound
from aether_runtime.domain.agent import AgentDefinition

from apps.api.tests.fakes import FakeAgentRepository


def _definition(**overrides: Any) -> AgentDefinition:
    payload: dict[str, Any] = {"schema_version": 1, "system_prompt": "You are a helper."}
    payload.update(overrides)
    return AgentDefinition.model_validate(payload)


def test_get_agent_returns_detail_with_definition_and_versions() -> None:
    """spec 0002 2.2: `GET /agents/{id}` 의 근거 — definition·versions 를 함께 채웁니다."""
    repo = FakeAgentRepository()
    create_agent = CreateAgentUseCase(repo)
    get_agent = GetAgentUseCase(repo)
    agent = create_agent("weather-bot", _definition(system_prompt="v1 prompt"))

    detail = get_agent(agent.id)

    assert detail.agent.id == agent.id
    assert detail.definition.system_prompt == "v1 prompt"
    assert [v.version for v in detail.versions] == [1]


def test_get_agent_after_update_reflects_current_version_definition() -> None:
    """spec 0002 R-1: 수정 뒤 `GET` 은 최신 버전(2)의 정의를 돌려줍니다."""
    repo = FakeAgentRepository()
    create_agent = CreateAgentUseCase(repo)
    update_agent = UpdateAgentUseCase(repo)
    get_agent = GetAgentUseCase(repo)
    agent = create_agent("weather-bot", _definition(system_prompt="v1 prompt"))
    update_agent(agent.id, _definition(system_prompt="v2 prompt"))

    detail = get_agent(agent.id)

    assert detail.agent.current_version == 2
    assert detail.definition.system_prompt == "v2 prompt"
    assert [v.version for v in detail.versions] == [1, 2]


def test_get_agent_missing_raises_agent_not_found() -> None:
    """spec 0002 2.2: 없는 `agent_id` 는 `404 agent_not_found` 의 근거가 되는 `AgentNotFound`."""
    repo = FakeAgentRepository()
    get_agent = GetAgentUseCase(repo)

    with pytest.raises(AgentNotFound):
        get_agent(uuid4())
