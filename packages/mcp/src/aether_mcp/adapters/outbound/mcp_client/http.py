"""spec 0003 2.2, D-1, 2.9: `McpClient` 포트를 streamable HTTP 전송으로 구현합니다.

`mcp` SDK import 는 이 파일 안에만 있습니다(AR-6, AR-9). 연결이 열린 뒤의 절차(도구
목록 변환, 타임아웃 강제, 결과 변환)는 `stdio.py` 와 함께 `_transport.py` 를
공유합니다 — 이 파일에 남는 것은 http 고유의 연결 방법(URL)뿐입니다. 호출마다 새로
연결합니다 — 연결 재사용은 spec 2.5(P2-2·P2-6)의 몫입니다.

`call` 은 `AETHER_MCP_CALL_TIMEOUT_MS`(spec 2.9, P2-2b)를 실제로 강제합니다 —
`asyncio.wait_for` 로 도구 호출 1회를 감싸고, 넘으면 (builtin) `TimeoutError` 를
그대로 올립니다. `stdio.py` 와 같은 방식입니다.
"""

from __future__ import annotations

import asyncio
from typing import Any

from mcp import Client

from aether_mcp.adapters.outbound.mcp_client import _transport
from aether_mcp.domain.tools import McpServerRef, Tool, ToolResult

_DEFAULT_CALL_TIMEOUT_MS = 30_000


class HttpMcpClient:
    """`McpClient` 포트 구현. `McpServerRef.transport == "http"` 만 받습니다."""

    def __init__(self, call_timeout_ms: int = _DEFAULT_CALL_TIMEOUT_MS) -> None:
        self._call_timeout_ms = call_timeout_ms

    def discover(self, server: McpServerRef) -> tuple[Tool, ...]:
        return asyncio.run(_transport.discover(lambda: Client(_url(server))))

    def call(self, server: McpServerRef, tool_name: str, arguments: dict[str, Any]) -> ToolResult:
        return asyncio.run(
            _transport.call(
                lambda: Client(_url(server)), tool_name, arguments, self._call_timeout_ms
            )
        )


def _url(server: McpServerRef) -> str:
    if server.transport != "http" or server.url is None:
        raise ValueError(f"HttpMcpClient requires an http McpServerRef, got {server!r}")
    return server.url
