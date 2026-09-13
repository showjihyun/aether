"""spec 0002 2.2 R-1, D-9: `CreateAgentUseCase` — Agent 와 Agent Version 1 을 함께 만듭니다.

`FakeAgentRepository` 하나로 컨테이너 없이 돕니다(architecture.md 3.1 "TDD" 이득).
"""

from __future__ import annotations

from typing import Any

import pytest
from aether_api.application.usecases.create_agent import CreateAgentUseCase
from aether_api.domain.agent import AgentNameTaken
from aether_runtime.domain.agent import AgentDefinition

from apps.api.tests.fakes import FakeAgentRepository


def _definition(**overrides: Any) -> AgentDefinition:
    payload: dict[str, Any] = {"schema_version": 1, "system_prompt": "You are a helper."}
    payload.update(overrides)
    return AgentDefinition.model_validate(payload)


def test_create_agent_returns_agent_with_version_1() -> None:
    """spec 0002 R-1: 생성은 `current_version == 1` 인 Agent 를 돌려줍니다."""
    repo = FakeAgentRepository()
    create_agent = CreateAgentUseCase(repo)

    agent = create_agent("weather-bot", _definition())

    assert agent.name == "weather-bot"
    assert agent.current_version == 1


def test_create_agent_persists_version_1_definition() -> None:
    """spec 0002 R-1: 만들어진 Version 1 의 정의가 요청한 정의와 같습니다."""
    repo = FakeAgentRepository()
    create_agent = CreateAgentUseCase(repo)

    agent = create_agent("weather-bot", _definition(system_prompt="v1 prompt"))
    version_1 = repo.get_version(agent.id, 1)

    assert version_1.definition.system_prompt == "v1 prompt"


def test_duplicate_name_raises_agent_name_taken() -> None:
    """spec 0002 2.2: 중복 이름은 `409 agent_name_taken` 의 근거가 되는 `AgentNameTaken`."""
    repo = FakeAgentRepository()
    create_agent = CreateAgentUseCase(repo)
    create_agent("weather-bot", _definition())

    with pytest.raises(AgentNameTaken):
        create_agent("weather-bot", _definition())
