"""spec 0002 2.2: `GetAgent` 포트의 구현.

현재 버전(`agent.current_version`)의 정의와 버전 이력을 합성합니다 — `AgentRepository`
가 이미 알고 있는 세 조회(`get`, `get_version`, `list_versions`)를 조합할 뿐, 새 SQL
을 만들지 않습니다.
"""

from __future__ import annotations

from uuid import UUID

from aether_api.application.ports.outbound.agent_repository import AgentRepository
from aether_api.domain.agent import AgentDetail


class GetAgentUseCase:
    """`AgentRepository` 하나로 inbound 포트 `GetAgent` 를 구현합니다."""

    def __init__(self, repository: AgentRepository) -> None:
        self._repository = repository

    def __call__(self, agent_id: UUID) -> AgentDetail:
        agent = self._repository.get(agent_id)
        current_version = self._repository.get_version(agent_id, agent.current_version)
        versions = self._repository.list_versions(agent_id)
        return AgentDetail(agent=agent, definition=current_version.definition, versions=versions)
