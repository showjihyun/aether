"""spec 0003 2.4, D-6 (🔒 P2-4): `JudgeToolCall` inbound 포트.

Gateway 유스케이스(P2-2b)가 **호출마다** 이 포트 하나만 불러 판정을 얻습니다(D-6, D-9)
— Run 단위 캐시가 없습니다. 자원 신분은 `(server_name, tool_name)` 이고 이름은 정확히
일치해야 합니다(정규화·와일드카드 없음).
"""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from aether_policy.domain.decision import Decision


class JudgeToolCall(Protocol):
    """`agent_version_id` 가 `server_name`·`tool_name` 을 부를 수 있는지 판정합니다."""

    def __call__(self, agent_version_id: UUID, server_name: str, tool_name: str) -> Decision: ...
