"""spec 0003 2.2, D-1, 2.9: `McpClient` 포트를 stdio 전송으로 구현합니다.

`mcp` SDK import 는 이 파일 안에만 있습니다(AR-6, AR-9) — `domain`·`application` 은
이 어댑터를 모르고 `McpClient` 포트로만 만납니다. 연결이 열린 뒤의 절차(도구 목록
변환, 타임아웃 강제, 결과 변환)는 `http.py` 와 함께 `_transport.py` 를 공유합니다 —
이 파일에 남는 것은 stdio 고유의 연결 방법(`StdioServerParameters`)뿐입니다.

호출마다 서버 프로세스를 새로 연결하고 닫습니다. 연결을 Run 수명에 묶어 재사용하는
것은 spec 2.5(P2-2·P2-6)의 몫이고 이 단위(P2-1)의 범위 밖입니다.

`call` 은 `AETHER_MCP_CALL_TIMEOUT_MS`(spec 2.9, P2-2b)를 실제로 강제합니다 —
`asyncio.wait_for` 로 도구 호출 1회를 감싸고, 넘으면 (builtin) `TimeoutError` 를
그대로 올립니다. `CallToolUseCase`(P2-2b)가 그것을 다른 실패와 같은 방식으로
`ToolCallFailed` 로 감싸고 감사에 `error_kind` 를 남깁니다 — 시계로 사후 판정하지
않고 여기서 실제로 끊습니다.
"""

from __future__ import annotations

import asyncio
from typing import Any

from mcp import Client, StdioServerParameters

from aether_mcp.adapters.outbound.mcp_client import _transport
from aether_mcp.domain.tools import McpServerRef, Tool, ToolResult

_DEFAULT_CALL_TIMEOUT_MS = 30_000


class StdioMcpClient:
    """`McpClient` 포트 구현. `McpServerRef.transport == "stdio"` 만 받습니다."""

    def __init__(self, call_timeout_ms: int = _DEFAULT_CALL_TIMEOUT_MS) -> None:
        self._call_timeout_ms = call_timeout_ms

    def discover(self, server: McpServerRef) -> tuple[Tool, ...]:
        return asyncio.run(_transport.discover(lambda: Client(_params(server))))

    def call(self, server: McpServerRef, tool_name: str, arguments: dict[str, Any]) -> ToolResult:
        return asyncio.run(
            _transport.call(
                lambda: Client(_params(server)), tool_name, arguments, self._call_timeout_ms
            )
        )


def _params(server: McpServerRef) -> StdioServerParameters:
    if server.transport != "stdio" or server.command is None:
        raise ValueError(f"StdioMcpClient requires a stdio McpServerRef, got {server!r}")
    return StdioServerParameters(command=server.command, args=list(server.args), env=server.env)
