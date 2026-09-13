"""spec 0002 2.2 R-1: `GetAgentVersion` 포트의 구현."""

from __future__ import annotations

from uuid import UUID

from aether_api.application.ports.outbound.agent_repository import AgentRepository
from aether_api.domain.agent import AgentVersion


class GetAgentVersionUseCase:
    """`AgentRepository` 하나로 inbound 포트 `GetAgentVersion` 을 구현합니다."""

    def __init__(self, repository: AgentRepository) -> None:
        self._repository = repository

    def __call__(self, agent_id: UUID, version: int) -> AgentVersion:
        return self._repository.get_version(agent_id, version)
