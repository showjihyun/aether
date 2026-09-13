"""spec 0002 2.1, 2.10, D-9: Control Plane 의 `Agent`·`Agent Version` 값 객체와 예외.

`AgentDefinition` 은 `aether_runtime.domain.agent` 의 것을 그대로 씁니다 — api 는
`aether_runtime.domain` 만 import 할 수 있고(AR-7 확장, `.importlinter` H-4) 그 타입을
복제하지 않습니다. `Agent`(정의)와 `Agent Version`(그 정의의 불변 스냅숏)과 `Run`(실행)을
혼용하지 않습니다([../../../../docs/domain.md](../../../../../docs/domain.md) 1절).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from aether_runtime.domain.agent import AgentDefinition


@dataclass(frozen=True)
class Agent:
    """`control.agents` 한 행. `current_version` 은 조회의 정본입니다(spec 2.10)."""

    id: UUID
    name: str
    current_version: int
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class AgentVersionSummary:
    """`GET /agents/{id}` 의 `versions[]` 원소 — 버전 번호와 생성 시각만."""

    version: int
    created_at: datetime


@dataclass(frozen=True)
class AgentVersion:
    """`control.agent_versions` 한 행. 생성된 뒤에는 불변(DB 트리거가 보장, spec 0001 R-8)."""

    agent_id: UUID
    version: int
    definition: AgentDefinition
    created_at: datetime


@dataclass(frozen=True)
class AgentPage:
    """`GET /agents` 의 커서 페이지 — `next_cursor` 는 불투명 문자열입니다."""

    items: list[Agent]
    next_cursor: str | None


@dataclass(frozen=True)
class AgentDetail:
    """`GET /agents/{id}` 와 `PUT /agents/{id}` 가 함께 돌려주는 합성 값."""

    agent: Agent
    definition: AgentDefinition
    versions: list[AgentVersionSummary]


class AgentNotFound(Exception):
    """주어진 `agent_id` 의 Agent 가 없습니다(spec 2.2 `404 agent_not_found`)."""


class AgentVersionNotFound(Exception):
    """Agent 는 있지만 주어진 `version` 이 없습니다(spec 2.2 `404 agent_version_not_found`)."""


class AgentNameTaken(Exception):
    """`control.agents.name` 의 UNIQUE 제약 위반(spec 2.2 `409 agent_name_taken`)."""


class AgentVersionConflict(Exception):
    """동시 수정으로 인한 `agent_versions` unique 위반 — 잠금 밖 경로.

    spec 2.2 `409 agent_version_conflict`.
    """
