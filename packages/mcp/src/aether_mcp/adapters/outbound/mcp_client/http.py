"""spec 0003 2.2, D-1: `McpClient` 포트를 streamable HTTP 전송으로 구현합니다.

`mcp` SDK import 는 이 파일 안에만 있습니다(AR-6, AR-9). 호출마다 새로 연결합니다
— 연결 재사용은 spec 2.5(P2-2·P2-6)의 몫입니다.
"""

from __future__ import annotations

import asyncio
from typing import Any

from mcp import Client

from aether_mcp.adapters.outbound.mcp_client._content import extract_text
from aether_mcp.domain.tools import McpServerRef, Tool, ToolResult


class HttpMcpClient:
    """`McpClient` 포트 구현. `McpServerRef.transport == "http"` 만 받습니다."""

    def discover(self, server: McpServerRef) -> tuple[Tool, ...]:
        return asyncio.run(self._discover(server))

    def call(self, server: McpServerRef, tool_name: str, arguments: dict[str, Any]) -> ToolResult:
        return asyncio.run(self._call(server, tool_name, arguments))

    async def _discover(self, server: McpServerRef) -> tuple[Tool, ...]:
        async with Client(_url(server)) as client:
            result = await client.list_tools()
            return tuple(
                Tool(
                    name=tool.name,
                    description=tool.description or "",
                    input_schema=tool.input_schema,
                )
                for tool in result.tools
            )

    async def _call(
        self, server: McpServerRef, tool_name: str, arguments: dict[str, Any]
    ) -> ToolResult:
        async with Client(_url(server)) as client:
            result = await client.call_tool(tool_name, arguments)
            return ToolResult(content=extract_text(result), is_error=result.is_error)


def _url(server: McpServerRef) -> str:
    if server.transport != "http" or server.url is None:
        raise ValueError(f"HttpMcpClient requires an http McpServerRef, got {server!r}")
    return server.url
