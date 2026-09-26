"""spec 0003 2.7, D-6, 개정 4: `control.tool_permissions` 에 대한 outbound 포트.

`PermissionTable` 의 fake 구현과 PostgreSQL 구현(`adapters/outbound/permission_table/
postgres.py`)은 같은 계약을 지킵니다 — 행이 없으면 `None` 을 돌려줄 뿐 기본값을
결정하지 않습니다. 기본값 deny 를 정하는 것은 `JudgeToolCallUseCase`(application)의
책임입니다(AR-9 — outbound 포트는 저장소 사실만 전달).
"""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from aether_policy.domain.decision import Decision


class PermissionTable(Protocol):
    """`(agent_version_id, server_name, tool_name)` 복합키로 선언된 판정을 찾습니다."""

    def lookup(self, agent_version_id: UUID, server_name: str, tool_name: str) -> Decision | None:
        """행이 있으면 그 `decision`, 없으면 `None`."""
        ...
