"""spec 0003 2.14, D-14 (🔒 P2-4): `SetToolPermission` inbound 포트.

CLI 어댑터(`aether-api permissions allow|deny`)가 이 포트 타입만 보고 부릅니다
(AR-12) — `agents get-version` 과 같은 `(agent_id, version)` 해석을 거쳐
`agent_version_id` 를 얻은 뒤 정책 표에 한 행을 씁니다. Agent 나 버전이 없으면
`agents_get_version` 과 같은 예외(`AgentNotFound`·`AgentVersionNotFound`)를 던집니다.
"""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from aether_policy.domain.decision import Decision


class SetToolPermission(Protocol):
    """`(agent_id, version)` 을 해석해 `(server_name, tool_name)` 에 대한 판정을 선언합니다."""

    def __call__(
        self, agent_id: UUID, version: int, server_name: str, tool_name: str, decision: Decision
    ) -> None: ...
