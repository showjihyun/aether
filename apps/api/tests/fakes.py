"""spec 0001 2.9: `ApiKeyStore` 의 dict 기반 fake — 컨테이너 없는 유스케이스 테스트용.

`calls` 는 어떤 메서드가 어떤 인자로 불렸는지 순서대로 기록합니다.
`test_authenticate.py` 가 이것으로 "형식 불량 키는 store 를 조회하지 않는다"(spec 2.9,
열거 공격 표면 축소)를 증명합니다. 테스트 지원 코드이며 제품 코드가 아닙니다.

`clock` 은 `create`/`revoke` 가 시각을 얻는 유일한 통로입니다(spec 0002 R-11) — 테스트가
`datetime.now()` 와 실제 시간 경과 대신 주입한 시계를 전진시켜 "두 번째 revoke 가 첫
`revoked_at` 을 유지한다" 를 `sleep` 없이 결정적으로 증명할 수 있게 합니다
(`test_api_key_store_contract.py`).
"""

from __future__ import annotations

import builtins
from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime
from uuid import UUID, uuid4

from aether_api.domain.agent import (
    Agent,
    AgentDetail,
    AgentNameTaken,
    AgentNotFound,
    AgentPage,
    AgentVersion,
    AgentVersionNotFound,
    AgentVersionSummary,
)
from aether_api.domain.api_key import ApiKey
from aether_runtime.domain.agent import AgentDefinition


def _default_clock() -> datetime:
    return datetime.now(UTC)


class FakeApiKeyStore:
    """`ApiKeyStore` 포트 계약의 인메모리 구현."""

    def __init__(self, clock: Callable[[], datetime] = _default_clock) -> None:
        self._by_id: dict[UUID, ApiKey] = {}
        self._id_by_hash: dict[str, UUID] = {}
        self.calls: list[tuple[str, str]] = []
        self._clock = clock

    def find_by_hash(self, key_hash: str) -> ApiKey | None:
        self.calls.append(("find_by_hash", key_hash))
        key_id = self._id_by_hash.get(key_hash)
        if key_id is None:
            return None
        return self._by_id[key_id]

    def create(self, label: str, key_hash: str) -> ApiKey:
        self.calls.append(("create", key_hash))
        if key_hash in self._id_by_hash:
            raise ValueError(f"duplicate key_hash: {key_hash!r}")
        key = ApiKey(
            id=uuid4(),
            label=label,
            key_hash=key_hash,
            created_at=self._clock(),
            revoked_at=None,
        )
        self._by_id[key.id] = key
        self._id_by_hash[key_hash] = key.id
        return key

    def revoke(self, key_id: UUID) -> None:
        """멱등: 이미 폐기된 키는 `revoked_at` 을 그대로 둡니다. 없는 id 는 `KeyError`."""
        self.calls.append(("revoke", str(key_id)))
        existing = self._by_id[key_id]  # 없으면 KeyError — 포트 계약(spec 2.9 H-3)
        if existing.revoked_at is None:
            self._by_id[key_id] = replace(existing, revoked_at=self._clock())

    # 테스트 준비 편의 — 포트 계약에는 없습니다.
    def seed(self, key: ApiKey) -> None:
        self._by_id[key.id] = key
        self._id_by_hash[key.key_hash] = key.id


class FakeAgentRepository:
    """`AgentRepository` 포트 계약(spec 0002 2.1 outbound)의 인메모리 구현.

    `add_version` 은 `current_version + 1` 로 순차 증가합니다(P1-1 usecase 테스트).
    커서(`list`)는 정렬된 목록의 정수 오프셋을 문자열로 감싼 것뿐입니다 — 불투명
    문자열이라는 계약만 지키면 되고, PostgreSQL 구현의 `(created_at, id)` 인코딩과
    같을 필요는 없습니다.
    """

    def __init__(self, clock: Callable[[], datetime] = _default_clock) -> None:
        self._agents: dict[UUID, Agent] = {}
        self._versions: dict[UUID, dict[int, AgentVersion]] = {}
        self._id_by_name: dict[str, UUID] = {}
        self._clock = clock

    def create(self, name: str, definition: AgentDefinition) -> Agent:
        if name in self._id_by_name:
            raise AgentNameTaken(name)
        agent_id = uuid4()
        now = self._clock()
        agent = Agent(id=agent_id, name=name, current_version=1, created_at=now, updated_at=now)
        self._agents[agent_id] = agent
        self._id_by_name[name] = agent_id
        self._versions[agent_id] = {
            1: AgentVersion(agent_id=agent_id, version=1, definition=definition, created_at=now)
        }
        return agent

    def get(self, agent_id: UUID) -> Agent:
        agent = self._agents.get(agent_id)
        if agent is None:
            raise AgentNotFound(agent_id)
        return agent

    def list(self, limit: int, cursor: str | None) -> AgentPage:
        ordered = sorted(self._agents.values(), key=lambda a: (a.created_at, str(a.id)))
        start = int(cursor) if cursor is not None else 0
        page_items = ordered[start : start + limit]
        end = start + len(page_items)
        next_cursor = str(end) if end < len(ordered) else None
        return AgentPage(items=page_items, next_cursor=next_cursor)

    def get_version(self, agent_id: UUID, version: int) -> AgentVersion:
        if agent_id not in self._agents:
            raise AgentNotFound(agent_id)
        found = self._versions[agent_id].get(version)
        if found is None:
            raise AgentVersionNotFound((agent_id, version))
        return found

    def list_versions(self, agent_id: UUID) -> builtins.list[AgentVersionSummary]:
        """`builtins.list` — 이 클래스의 `list` 메서드가 클래스 본문에서 내장 `list` 를 가립니다."""
        if agent_id not in self._agents:
            raise AgentNotFound(agent_id)
        versions = sorted(self._versions[agent_id].values(), key=lambda v: v.version)
        return [AgentVersionSummary(version=v.version, created_at=v.created_at) for v in versions]

    def add_version(self, agent_id: UUID, definition: AgentDefinition) -> AgentDetail:
        agent = self._agents.get(agent_id)
        if agent is None:
            raise AgentNotFound(agent_id)
        new_version_number = agent.current_version + 1
        now = self._clock()
        new_version = AgentVersion(
            agent_id=agent_id, version=new_version_number, definition=definition, created_at=now
        )
        self._versions[agent_id][new_version_number] = new_version
        updated_agent = replace(agent, current_version=new_version_number, updated_at=now)
        self._agents[agent_id] = updated_agent
        versions = sorted(self._versions[agent_id].values(), key=lambda v: v.version)
        return AgentDetail(
            agent=updated_agent,
            definition=definition,
            versions=[
                AgentVersionSummary(version=v.version, created_at=v.created_at) for v in versions
            ],
        )
