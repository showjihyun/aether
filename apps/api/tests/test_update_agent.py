"""spec 0002 2.2 R-1, D-9: `UpdateAgentUseCase` — `definition` 만 바뀌고 `name` 은 불변."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

import pytest
from aether_api.application.usecases.create_agent import CreateAgentUseCase
from aether_api.application.usecases.update_agent import UpdateAgentUseCase
from aether_api.domain.agent import AgentNotFound
from aether_runtime.domain.agent import AgentDefinition

from apps.api.tests.fakes import FakeAgentRepository


def _definition(**overrides: Any) -> AgentDefinition:
    payload: dict[str, Any] = {"schema_version": 1, "system_prompt": "You are a helper."}
    payload.update(overrides)
    return AgentDefinition.model_validate(payload)


def test_update_agent_creates_version_2_and_keeps_name() -> None:
    """spec 0002 D-9: `PUT` 은 `definition` 만 바꿉니다 — `name` 은 Phase 1 불변."""
    repo = FakeAgentRepository()
    create_agent = CreateAgentUseCase(repo)
    update_agent = UpdateAgentUseCase(repo)
    agent = create_agent("weather-bot", _definition())

    detail = update_agent(agent.id, _definition(system_prompt="v2 prompt"))

    assert detail.agent.name == "weather-bot"
    assert detail.agent.current_version == 2
    assert detail.definition.system_prompt == "v2 prompt"
    assert [v.version for v in detail.versions] == [1, 2]


def test_update_agent_twice_reaches_version_3() -> None:
    repo = FakeAgentRepository()
    create_agent = CreateAgentUseCase(repo)
    update_agent = UpdateAgentUseCase(repo)
    agent = create_agent("weather-bot", _definition())

    update_agent(agent.id, _definition(system_prompt="v2 prompt"))
    detail = update_agent(agent.id, _definition(system_prompt="v3 prompt"))

    assert detail.agent.current_version == 3
    assert [v.version for v in detail.versions] == [1, 2, 3]


def test_update_agent_missing_raises_agent_not_found() -> None:
    """spec 0002 2.2: 없는 `agent_id` 는 `404 agent_not_found` 의 근거가 되는 `AgentNotFound`."""
    repo = FakeAgentRepository()
    update_agent = UpdateAgentUseCase(repo)

    with pytest.raises(AgentNotFound):
        update_agent(uuid4(), _definition())
