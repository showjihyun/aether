"""spec 0003 2.4, D-6 (🔒 P2-4): `JudgeToolCallUseCase` — `JudgeToolCall` 의 유일한 구현.

**기본값은 deny 입니다(허용 목록)** — 표에 행이 없으면 `PermissionTable.lookup` 이
`None` 을 돌려주고, 이 유스케이스가 그것을 `deny` 로 바꿉니다. 이름은 정확히 일치
(대소문자·공백 정규화 없음, 와일드카드 없음, D-6)이므로 정규화는 이 클래스도,
`PermissionTable` 구현도 하지 않습니다 — 호출자가 이미 정확한 `server_name`·
`tool_name` 을 건넨다고 가정합니다.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from aether_policy.application.ports.outbound.permission_table import PermissionTable
from aether_policy.domain.decision import Decision

_DEFAULT_DECISION: Decision = "deny"


@dataclass
class JudgeToolCallUseCase:
    table: PermissionTable

    def __call__(self, agent_version_id: UUID, server_name: str, tool_name: str) -> Decision:
        decision = self.table.lookup(agent_version_id, server_name, tool_name)
        if decision is None:
            return _DEFAULT_DECISION
        return decision
