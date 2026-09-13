"""spec 0002 2.1, 2.2, D-9: Agent Registry 유스케이스 인터페이스.

HTTP 어댑터(`adapters/inbound/http/agents.py`)는 이 포트 타입만 보고 부릅니다(AR-12) —
구현(`application/usecases/*.py`)은 조립(`main.py`)이 건네줍니다.
"""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from aether_runtime.domain.agent import AgentDefinition

from aether_api.domain.agent import Agent, AgentDetail, AgentPage, AgentVersion


class CreateAgent(Protocol):
    """`name` 으로 Agent 를 만들고 `definition` 으로 Version 1 을 함께 만듭니다.

    이름이 이미 있으면 `AgentNameTaken` 을 던집니다.
    """

    def __call__(self, name: str, definition: AgentDefinition) -> Agent: ...


class ListAgents(Protocol):
    """`cursor` 이후 최대 `limit` 개의 Agent 를 돌려줍니다."""

    def __call__(self, limit: int, cursor: str | None) -> AgentPage: ...


class GetAgent(Protocol):
    """Agent 와 현재 버전의 정의, 버전 이력을 함께 돌려줍니다.

    없으면 `AgentNotFound` 를 던집니다.
    """

    def __call__(self, agent_id: UUID) -> AgentDetail: ...


class GetAgentVersion(Protocol):
    """특정 `version` 의 불변 정의를 돌려줍니다.

    Agent 가 없으면 `AgentNotFound`, 버전이 없으면 `AgentVersionNotFound` 를 던집니다.
    """

    def __call__(self, agent_id: UUID, version: int) -> AgentVersion: ...


class UpdateAgent(Protocol):
    """`definition` 으로 새 버전을 만듭니다. `name` 은 바꾸지 않습니다(Phase 1 불변, D-9).

    없으면 `AgentNotFound`, 동시 수정 충돌이면 `AgentVersionConflict` 를 던집니다.
    """

    def __call__(self, agent_id: UUID, definition: AgentDefinition) -> AgentDetail: ...
