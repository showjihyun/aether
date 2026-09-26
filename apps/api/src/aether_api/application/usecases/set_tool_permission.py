"""spec 0003 2.14, D-14 (🔒 P2-4): `SetToolPermissionUseCase` — `SetToolPermission` 의
유일한 구현.

`GetAgentVersion`(기존 포트)으로 `(agent_id, version)` → `agent_version_id` 를 해석하고
(존재하지 않으면 `AgentNotFound`/`AgentVersionNotFound` 가 그대로 전파됩니다),
`ToolPermissionStore` 로 한 행을 씁니다(upsert). 표준 라이브러리와 `application.ports`
만 import 합니다(AR-9).
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from aether_policy.domain.decision import Decision

from aether_api.application.ports.inbound.agents import GetAgentVersion
from aether_api.application.ports.outbound.tool_permissions import ToolPermissionStore


@dataclass
class SetToolPermissionUseCase:
    get_agent_version: GetAgentVersion
    store: ToolPermissionStore

    def __call__(
        self, agent_id: UUID, version: int, server_name: str, tool_name: str, decision: Decision
    ) -> None:
        agent_version = self.get_agent_version(agent_id, version)
        self.store.upsert(agent_version.id, server_name, tool_name, decision)
