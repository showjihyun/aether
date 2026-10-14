"""spec 0005 2.5 개정 3, 2.9 개정 2 (P4-2a B2): `AgentRunReader` - 자식 Agent Run 의 상태와 Agent
Version 해석을 **읽기만** 합니다.

어댑터는 `data.run_executions`(worker 가 소유하는 평면 - 자식의 실행 상태 정본)와
`control.agent_versions`(`aether_data` 는 SELECT 가 있습니다, 0001)를 읽습니다. `control.runs` 의
투영을 기다리지 않습니다.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from aether_runtime.domain.run import RunStatus


@dataclass(frozen=True)
class AgentVersionRef:
    """해석된 Agent Version - `agent_version_id` 가 자식 Run 선언의 FK 입니다."""

    agent_version_id: UUID
    version: int


class AgentRunReader(Protocol):
    def status(self, agent_run_id: UUID) -> RunStatus | None:
        """자식 Run 의 실행 상태. 아직 worker 가 집지 않아 실행 행이 없으면 `None` - "종결 아님"
        과 같이 다룹니다."""
        ...

    def version_for(self, agent_id: UUID, version: int | None) -> AgentVersionRef | None:
        """`version` 이 `None` 이면 그 Agent 의 **최대 version** 입니다. `control.agents.
        current_version` 은 worker 가 읽을 수 없고, Version 은 append-only(불변 트리거)이므로 최대
        version 이 곧 현재 version 입니다. 없으면 `None`."""
        ...
