"""spec 0002 2.1, 2.2, 2.10, D-9: `control.agents`·`control.agent_versions` 에 대한 outbound 포트.

`AgentRepository` 의 fake 구현(`apps/api/tests/fakes.py`)과 PostgreSQL 구현
(`adapters/outbound/db/agent_repository.py`)은 같은 포트 계약을 만족해야 합니다
(architecture.md 3.1 "TDD" 이득 — 포트 계약 테스트).
"""

from __future__ import annotations

import builtins
from typing import Protocol
from uuid import UUID

from aether_runtime.domain.agent import AgentDefinition

from aether_api.domain.agent import Agent, AgentDetail, AgentPage, AgentVersion, AgentVersionSummary


class AgentRepository(Protocol):
    """`control.agents`·`control.agent_versions` 저장소 계약."""

    def create(self, name: str, definition: AgentDefinition) -> Agent:
        """`agents` 행과 Version 1 을 **한 트랜잭션에** 만듭니다.

        이름이 이미 있으면 `AgentNameTaken` 을 던집니다.
        """
        ...

    def get(self, agent_id: UUID) -> Agent:
        """없으면 `AgentNotFound` 를 던집니다."""
        ...

    def list(self, limit: int, cursor: str | None) -> AgentPage:
        """`cursor` 이후 최대 `limit` 개. `next_cursor` 는 불투명 문자열입니다."""
        ...

    def get_version(self, agent_id: UUID, version: int) -> AgentVersion:
        """Agent 가 없으면 `AgentNotFound`, 버전이 없으면 `AgentVersionNotFound`."""
        ...

    def list_versions(self, agent_id: UUID) -> builtins.list[AgentVersionSummary]:
        """없으면 `AgentNotFound`.

        `builtins.list` 로 완전히 씁니다 — 이 클래스에 `list` 라는 메서드가 있어서
        (바로 위) 그 이름이 이 클래스 본문 안에서 내장 `list` 를 가립니다(mypy
        `valid-type` 오류로 확인).
        """
        ...

    def add_version(self, agent_id: UUID, definition: AgentDefinition) -> AgentDetail:
        """**한 트랜잭션에서** `agents` 행을 `SELECT … FOR UPDATE` 로 잠근 뒤

        `current_version + 1` 로 새 버전을 넣고 `agents.current_version`·`updated_at`
        을 갱신합니다. 없으면 `AgentNotFound`, unique 위반(잠금 밖 경로)이면
        `AgentVersionConflict` 를 던집니다.
        """
        ...
