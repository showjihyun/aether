"""spec 0003 2.4, D-9: `CallTool` inbound 포트 — Gateway 유스케이스의 유일한 진입점.

`runtime`(P2-3)은 이 포트의 **타입만** 봅니다(AR-12). 구현 조립은 worker 의
`main`(P2-3·P2-6)이 합니다.
"""

from __future__ import annotations

from typing import Protocol

from aether_mcp.domain.tools import ToolCall, ToolResult


class CallTool(Protocol):
    def __call__(self, call: ToolCall) -> ToolResult:
        """판정 → 호출 → 감사(spec 2.4)의 고정 순서로 도구를 한 번 부릅니다.

        deny 면 `ToolCallDenied`, 클라이언트 호출이 실패하면 `ToolCallFailed`,
        도구가 없거나 서버가 연결 실패로 제거되었으면 `ToolNotFound` 를 올립니다.
        세 경우 모두 그 전에 감사 1건이 기록됩니다.
        """
        ...
