"""spec 0003 2.9: `HttpMcpClient.call` 이 `AETHER_MCP_CALL_TIMEOUT_MS` 를 실제로
강제하는지 — 응답하지 않는 fake 전송(`asyncio.Event`)과 아주 작은 상한(50ms)으로
결정적으로 재현합니다. `sleep` 을 쓰지 않습니다.
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest
from aether_mcp.adapters.outbound.mcp_client import http as http_module
from aether_mcp.adapters.outbound.mcp_client.http import HttpMcpClient
from aether_mcp.domain.tools import McpServerRef


class _HangingClient:
    """`mcp.Client` 를 흉내 냅니다 — `call_tool` 이 절대 끝나지 않는 대기로 걸립니다."""

    async def __aenter__(self) -> _HangingClient:
        return self

    async def __aexit__(self, *exc_info: Any) -> None:
        return None

    async def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> Any:
        await asyncio.Event().wait()  # 절대 set 되지 않음 — sleep 이 아니라 이벤트로 막음
        raise AssertionError("unreachable — wait_for 가 먼저 끊어야 합니다")


def _server() -> McpServerRef:
    return McpServerRef(name="hanging", transport="http", url="http://127.0.0.1:1/mcp")


def test_call_times_out_deterministically_without_real_sleep(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(http_module, "Client", lambda url: _HangingClient())
    client = HttpMcpClient(call_timeout_ms=50)

    with pytest.raises(TimeoutError):
        client.call(_server(), "whatever", {})
