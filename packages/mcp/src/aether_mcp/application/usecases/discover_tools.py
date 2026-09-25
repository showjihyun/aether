"""spec 0003 2.2, R-1: `DiscoverToolsUseCase` — `DiscoverTools`(inbound) 의 유일한 구현.

`McpClient`(outbound) 만 통해 바깥을 봅니다(AR-8, AR-9) — SDK 를 모릅니다.
"""

from __future__ import annotations

from dataclasses import dataclass

from aether_mcp.application.ports.outbound.mcp_client import McpClient
from aether_mcp.domain.tools import McpServerRef, Tool


@dataclass
class DiscoverToolsUseCase:
    client: McpClient

    def __call__(self, server: McpServerRef) -> tuple[Tool, ...]:
        return self.client.discover(server)
