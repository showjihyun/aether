"""spec 0003 2.1, AR-6, AR-12, D-9: `McpToolGateway` — `ToolGateway`(outbound) 의
유일한 구현. `aether_mcp` 의 **inbound 포트 타입만** 봅니다 — `CallTool`·
`DiscoverTools` 의 Protocol 타입과 `domain` 값 타입만 import 하고, `aether_mcp.
adapters`·`aether_mcp.application.usecases` 는 import 하지 않습니다(실제 구현
조립은 worker 의 `main.py` 가 맡습니다, AR-10).

바인딩(`AgentDefinition.mcp_servers`)은 P2-6 의 범위입니다 — 이 단위는 조립 시점에
고정된 `server`(`McpServerRef`) 하나로 모든 호출을 라우팅합니다(D-5, 저장소 안
`tools/mcp-servers/builtin/` 서버).

예외 변환(spec 2.4, 2.5): `aether_mcp.domain.errors` 의 `ToolCallDenied`·
`ToolCallFailed`·`ToolNotFound` 를 이 패키지의 같은 이름 예외로 바꿔 다시 던집니다
— Executor 는 `aether_mcp` 를 몰라도 됩니다. 그 밖의 예외(변환 대상이 아닌 것)는
그대로 전파합니다.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from aether_mcp.application.ports.inbound.call_tool import CallTool
from aether_mcp.application.ports.inbound.discover_tools import DiscoverTools
from aether_mcp.domain.errors import ToolCallDenied as McpToolCallDenied
from aether_mcp.domain.errors import ToolCallFailed as McpToolCallFailed
from aether_mcp.domain.errors import ToolNotFound as McpToolNotFound
from aether_mcp.domain.tools import McpServerRef
from aether_mcp.domain.tools import ToolCall as McpToolCall

from aether_runtime.application.ports.outbound.model_gateway import ToolSchema
from aether_runtime.application.ports.outbound.tool_gateway import (
    ToolCallDenied,
    ToolCallFailed,
    ToolNotFound,
)
from aether_runtime.domain.tools import ToolResult


class McpToolGateway:
    """`ToolGateway` 포트 구현 — 고정된 `server` 하나로 `CallTool`·`DiscoverTools`
    (둘 다 `aether_mcp` inbound 포트) 를 부릅니다."""

    def __init__(
        self, *, call_tool: CallTool, discover_tools: DiscoverTools, server: McpServerRef
    ) -> None:
        self._call_tool = call_tool
        self._discover_tools = discover_tools
        self._server = server

    def discover(self) -> tuple[ToolSchema, ...]:
        tools = self._discover_tools(self._server)
        return tuple(
            ToolSchema(name=tool.name, description=tool.description, input_schema=tool.input_schema)
            for tool in tools
        )

    def call(
        self, run_id: UUID, agent_version_id: UUID, name: str, arguments: dict[str, Any]
    ) -> ToolResult:
        call = McpToolCall(
            run_id=run_id,
            agent_version_id=agent_version_id,
            server=self._server,
            tool_name=name,
            arguments=arguments,
        )
        try:
            result = self._call_tool(call)
        except McpToolCallDenied as exc:
            raise ToolCallDenied(str(exc)) from exc
        except McpToolNotFound as exc:
            raise ToolNotFound(str(exc)) from exc
        except McpToolCallFailed as exc:
            raise ToolCallFailed(str(exc)) from exc
        return ToolResult(content=result.content, is_error=result.is_error)
