"""spec 0003 2.14, D-14 (🔒 P2-4): `control.tool_permissions` 선언을 쓰는 outbound 포트.

읽기(`aether_data`, 판정 시점)는 `aether_policy` 의 `PermissionTable` 이 소유합니다
(spec D-15). 이 포트는 그 반대편 — 선언을 **쓰는** 쪽(`aether_control`, CLI)만
다룹니다. 복합 PK `(agent_version_id, server_name, tool_name)` 을 그대로 덮어씁니다
(upsert, spec 개정 4).
"""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from aether_policy.domain.decision import Decision


class ToolPermissionStore(Protocol):
    """`control.tool_permissions` 에 대한 쓰기 계약."""

    def upsert(
        self, agent_version_id: UUID, server_name: str, tool_name: str, decision: Decision
    ) -> None:
        """같은 키(`agent_version_id`, `server_name`, `tool_name`)의 행을 만들거나 덮어씁니다."""
        ...
