"""spec 0002 R-1, D-9: `UpdateAgent` 포트의 구현 — `definition` 만 바꿉니다.

`name` 은 Phase 1 에서 불변입니다. 새 버전 번호와 `agents.current_version` 갱신은
저장소가 한 트랜잭션에서(`SELECT … FOR UPDATE`) 처리합니다(spec 2.2).
"""

from __future__ import annotations

from uuid import UUID

from aether_runtime.domain.agent import AgentDefinition

from aether_api.application.ports.outbound.agent_repository import AgentRepository
from aether_api.domain.agent import AgentDetail


class UpdateAgentUseCase:
    """`AgentRepository` 하나로 inbound 포트 `UpdateAgent` 를 구현합니다."""

    def __init__(self, repository: AgentRepository) -> None:
        self._repository = repository

    def __call__(self, agent_id: UUID, definition: AgentDefinition) -> AgentDetail:
        return self._repository.add_version(agent_id, definition)
