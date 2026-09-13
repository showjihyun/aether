"""spec 0002 2.2 R-1: `GetAgentVersionUseCase` — 특정 버전의 불변 정의를 돌려줍니다."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

import pytest
from aether_api.application.usecases.create_agent import CreateAgentUseCase
from aether_api.application.usecases.get_agent_version import GetAgentVersionUseCase
from aether_api.application.usecases.update_agent import UpdateAgentUseCase
from aether_api.domain.agent import AgentNotFound, AgentVersionNotFound
from aether_runtime.domain.agent import AgentDefinition

from apps.api.tests.fakes import FakeAgentRepository


def _definition(**overrides: Any) -> AgentDefinition:
    payload: dict[str, Any] = {"schema_version": 1, "system_prompt": "You are a helper."}
    payload.update(overrides)
    return AgentDefinition.model_validate(payload)


def test_get_agent_version_returns_that_versions_definition() -> None:
    repo = FakeAgentRepository()
    create_agent = CreateAgentUseCase(repo)
    get_agent_version = GetAgentVersionUseCase(repo)
    agent = create_agent("weather-bot", _definition(system_prompt="v1 prompt"))

    version = get_agent_version(agent.id, 1)

    assert version.version == 1
    assert version.definition.system_prompt == "v1 prompt"


def test_version_1_definition_unchanged_after_update() -> None:
    """spec 0002 R-1: 수정 뒤에도 Version 1 의 `definition` 은 생성 시 그대로입니다."""
    repo = FakeAgentRepository()
    create_agent = CreateAgentUseCase(repo)
    update_agent = UpdateAgentUseCase(repo)
    get_agent_version = GetAgentVersionUseCase(repo)
    agent = create_agent("weather-bot", _definition(system_prompt="v1 prompt"))

    update_agent(agent.id, _definition(system_prompt="v2 prompt"))
    version_1 = get_agent_version(agent.id, 1)

    assert version_1.definition.system_prompt == "v1 prompt"


def test_missing_version_raises_agent_version_not_found() -> None:
    repo = FakeAgentRepository()
    create_agent = CreateAgentUseCase(repo)
    get_agent_version = GetAgentVersionUseCase(repo)
    agent = create_agent("weather-bot", _definition())

    with pytest.raises(AgentVersionNotFound):
        get_agent_version(agent.id, 2)


def test_missing_agent_raises_agent_not_found() -> None:
    repo = FakeAgentRepository()
    get_agent_version = GetAgentVersionUseCase(repo)

    with pytest.raises(AgentNotFound):
        get_agent_version(uuid4(), 1)
