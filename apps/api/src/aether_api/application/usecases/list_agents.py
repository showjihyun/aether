"""spec 0002 2.2: `ListAgents` 포트의 구현."""

from __future__ import annotations

from aether_api.application.ports.outbound.agent_repository import AgentRepository
from aether_api.domain.agent import AgentPage


class ListAgentsUseCase:
    """`AgentRepository` 하나로 inbound 포트 `ListAgents` 를 구현합니다."""

    def __init__(self, repository: AgentRepository) -> None:
        self._repository = repository

    def __call__(self, limit: int, cursor: str | None, name: str | None = None) -> AgentPage:
        return self._repository.list(limit, cursor, name)
