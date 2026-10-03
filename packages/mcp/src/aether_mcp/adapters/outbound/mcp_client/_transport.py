"""`stdio.py`·`http.py` 공용: `Client` 연결 하나를 열어 discover/call 1회를 실행하는
비동기 로직. 두 어댑터의 유일한 차이는 그 연결을 어떻게 여는가(`StdioServerParameters`
대 URL)뿐이므로, 연결이 열린 뒤의 절차(도구 목록 변환, 타임아웃 강제, 결과 변환)는
여기 한 곳에 둡니다.

`Client` 생성 자체는 의도적으로 이 모듈이 하지 않습니다 — 호출자가 넘기는
`client_factory`(0-인자 콜러블) 안에서 만듭니다. 그래야 `mcp.Client` import 와
그 이름이 여전히 `stdio.py`/`http.py` 각자에 남고, 두 파일의 타임아웃 테스트가
`monkeypatch.setattr(stdio_module, "Client", ...)` 식으로 그 모듈의 `Client` 만
갈아 끼워도 그대로 통합니다.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from types import TracebackType
from typing import Any, Protocol

from aether_mcp.adapters.outbound.mcp_client._content import extract_text
from aether_mcp.domain.tools import Tool, ToolResult


class _AsyncMcpClient(Protocol):
    """`mcp.Client` 가 실제로 구현하는 것 중 이 모듈이 쓰는 부분만 뽑은 모양.
    테스트의 fake(`_HangingClient` 등)도 이 모양만 맞추면 됩니다."""

    async def __aenter__(self) -> _AsyncMcpClient: ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> bool | None: ...

    async def list_tools(self) -> Any: ...

    async def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> Any: ...


async def discover(client_factory: Callable[[], _AsyncMcpClient]) -> tuple[Tool, ...]:
    async with client_factory() as client:
        result = await client.list_tools()
        return tuple(
            Tool(
                name=tool.name,
                description=tool.description or "",
                input_schema=tool.input_schema,
            )
            for tool in result.tools
        )


async def call(
    client_factory: Callable[[], _AsyncMcpClient],
    tool_name: str,
    arguments: dict[str, Any],
    timeout_ms: int,
) -> ToolResult:
    async with client_factory() as client:
        result = await asyncio.wait_for(
            client.call_tool(tool_name, arguments), timeout=timeout_ms / 1000
        )
        return ToolResult(content=extract_text(result), is_error=result.is_error)
