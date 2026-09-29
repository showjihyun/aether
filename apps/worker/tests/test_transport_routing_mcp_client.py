"""spec 0003 2.2, 2.9 (plan 0003 P2-5 2단계): `_TransportRoutingMcpClient` —
`McpServerRef.transport` 에 따라 `StdioMcpClient`/`HttpMcpClient` 중 실제로 부를
클라이언트를 고릅니다.

`.importlinter` 의 `ar6-mcp-client-only-in-mcp` 예외가 `aether_worker.main ->
...mcp_client.stdio`·`...mcp_client.http` 정확히 둘만 허용하므로(사람 결정), 이
라우팅 클래스는 반드시 `aether_worker.main` 안에 있어야 합니다 — 다른 모듈로
옮기면 그 모듈이 새 import 경로가 되어 예외와 맞지 않아 `lint-imports` 가
"No matches for ignored import" 로 실패합니다.

여기서는 fake 클라이언트로 라우팅 로직만 검증합니다 — 실제 stdio/http 연결
자체는 P2-1(R-1)·이번 단위의 HTTP 통합 테스트가 판정합니다.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from aether_mcp.domain.tools import McpServerRef, Tool, ToolResult
from aether_worker.main import _TransportRoutingMcpClient


@dataclass
class _FakeClient:
    label: str
    calls: list[str] = field(default_factory=list)

    def discover(self, server: McpServerRef) -> tuple[Tool, ...]:
        self.calls.append("discover")
        return (Tool(name=f"{self.label}-tool", description=""),)

    def call(self, server: McpServerRef, tool_name: str, arguments: dict[str, Any]) -> ToolResult:
        self.calls.append("call")
        return ToolResult(content=self.label)


def test_discover_routes_a_stdio_server_to_the_stdio_client() -> None:
    stdio = _FakeClient("stdio")
    http = _FakeClient("http")
    router = _TransportRoutingMcpClient(stdio=stdio, http=http)  # type: ignore[arg-type]
    server = McpServerRef(name="x", transport="stdio", command="python")

    tools = router.discover(server)

    assert tools[0].name == "stdio-tool"
    assert stdio.calls == ["discover"]
    assert http.calls == []


def test_call_routes_an_http_server_to_the_http_client() -> None:
    stdio = _FakeClient("stdio")
    http = _FakeClient("http")
    router = _TransportRoutingMcpClient(stdio=stdio, http=http)  # type: ignore[arg-type]
    server = McpServerRef(name="y", transport="http", url="http://x")

    result = router.call(server, "tool", {})

    assert result.content == "http"
    assert http.calls == ["call"]
    assert stdio.calls == []
