"""spec 0003 R-1, 2.2: `DiscoverToolsUseCase` 는 `McpClient`(outbound) 의 `discover` 를
그대로 위임합니다 — fake 클라이언트로 컨테이너 없이 판정합니다.
"""

from __future__ import annotations

from aether_mcp.application.usecases.discover_tools import DiscoverToolsUseCase
from aether_mcp.domain.tools import McpServerRef, Tool

from tests.support.mcp_fakes import FakeMcpClient


def test_discover_tools_delegates_to_mcp_client() -> None:
    server = McpServerRef(name="echo", transport="stdio", command="python", args=("server.py",))
    tools = (
        Tool(name="echo", description="echoes input", input_schema={"type": "object"}),
        Tool(name="fail", description="always fails", input_schema={"type": "object"}),
    )
    client = FakeMcpClient(tools_by_server={server.name: tools})
    usecase = DiscoverToolsUseCase(client=client)

    result = usecase(server)

    assert result == tools
    assert client.discover_calls == [server]
