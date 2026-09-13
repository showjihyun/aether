"""spec 0002 R-1, D-9: `CreateAgent` 포트의 구현.

`domain`·`application.ports`·`aether_runtime.domain` 만 import 합니다(AR-9).
"""

from __future__ import annotations

from aether_runtime.domain.agent import AgentDefinition

from aether_api.application.ports.outbound.agent_repository import AgentRepository
from aether_api.domain.agent import Agent


class CreateAgentUseCase:
    """`AgentRepository` 하나로 inbound 포트 `CreateAgent` 를 구현합니다."""

    def __init__(self, repository: AgentRepository) -> None:
        self._repository = repository

    def __call__(self, name: str, definition: AgentDefinition) -> Agent:
        return self._repository.create(name, definition)
