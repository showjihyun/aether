"""도구 관련 outbound 포트 두 개의 공용 fake (improvement-log 2026-09-28-001).

포트에 메서드가 하나 늘면(예: P2-6 의 `ToolGateway.bind`/`close`) 그 포트를
구현하는 fake 가 흩어진 곳 전부를 기계적으로 고쳐야 했다 — `FakeMcpClient` 가
`packages/mcp/tests/` 세 파일에, `_SingleToolGateway` 가 `apps/api/tests/` 두
파일과 `packages/runtime/tests/test_policy.py` 에 각각 복제되어 있었다. 포트
하나당 fake 하나로 모으고, 시나리오 차이는 생성 인자로 준다.

- `FakeMcpClient` — `aether_mcp` 의 `McpClient` outbound 포트
  (`application/ports/outbound/mcp_client.py`)의 fake. 서버 이름으로 키를 둔
  `tools_by_server`/`call_results`/`call_exceptions`/`fail_discover_servers`
  로 세 테스트 파일이 쓰던 시나리오(정상 discover, 서버별 연결 실패, 호출 예외,
  호출 기록)를 모두 표현한다.
- `_SingleToolGateway` — `aether_runtime` 의 `ToolGateway` outbound 포트
  (`application/ports/outbound/tool_gateway.py`)의 최소 구현. 도구 객체 하나만
  알고(duck typing — `name`·`description`·`input_schema`·`run(arguments)`),
  그 이름이 아니면 `ToolNotFound` 를 올린다. `bind`/`close` 는 no-op.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol
from uuid import UUID

from aether_mcp.domain.tools import McpServerRef, Tool
from aether_mcp.domain.tools import ToolResult as McpToolResult
from aether_runtime.application.ports.outbound.model_gateway import ToolSchema
from aether_runtime.application.ports.outbound.tool_gateway import ToolNotFound
from aether_runtime.domain.tools import ToolResult


@dataclass
class FakeMcpClient:
    """`McpClient` 포트의 fake. 서버 이름이 키이므로 서버별로 다른 시나리오를
    섞어 쓸 수 있다(예: 한 서버는 연결 실패, 다른 서버는 정상)."""

    tools_by_server: dict[str, tuple[Tool, ...]] = field(default_factory=dict)
    fail_discover_servers: set[str] = field(default_factory=set)
    call_results: dict[str, McpToolResult] = field(default_factory=dict)
    call_exceptions: dict[str, Exception] = field(default_factory=dict)
    discover_calls: list[McpServerRef] = field(default_factory=list)
    call_calls: list[tuple[str, str]] = field(default_factory=list)

    def discover(self, server: McpServerRef) -> tuple[Tool, ...]:
        self.discover_calls.append(server)
        if server.name in self.fail_discover_servers:
            raise ConnectionError(f"cannot connect to {server.name}")
        return self.tools_by_server.get(server.name, ())

    def call(
        self, server: McpServerRef, tool_name: str, arguments: dict[str, Any]
    ) -> McpToolResult:
        self.call_calls.append((server.name, tool_name))
        if server.name in self.call_exceptions:
            raise self.call_exceptions[server.name]
        return self.call_results.get(server.name, McpToolResult(content="ok"))


class _SingleCallableTool(Protocol):
    """`_SingleToolGateway` 가 감싸는 도구의 모양 — 세 테스트 파일이 쓰던
    `_GatedClockTool`/`_FlakyTool` 등이 전부 이 모양이다."""

    name: str
    description: str
    input_schema: dict[str, Any]

    def run(self, arguments: dict[str, Any]) -> ToolResult: ...


class _SingleToolGateway:
    """`ToolGateway` 포트의 최소 구현 — 도구 하나만 안다(spec 0003 2.1)."""

    def __init__(self, tool: _SingleCallableTool) -> None:
        self._tool = tool

    def bind(self, mcp_servers: tuple[Any, ...]) -> None:
        del mcp_servers

    def close(self) -> None:
        pass

    def discover(self) -> tuple[ToolSchema, ...]:
        return (
            ToolSchema(
                name=self._tool.name,
                description=self._tool.description,
                input_schema=self._tool.input_schema,
            ),
        )

    def call(
        self, run_id: UUID, agent_version_id: UUID, name: str, arguments: dict[str, Any]
    ) -> ToolResult:
        del run_id, agent_version_id
        if name != self._tool.name:
            raise ToolNotFound(name)
        result: ToolResult = self._tool.run(arguments)
        return result
