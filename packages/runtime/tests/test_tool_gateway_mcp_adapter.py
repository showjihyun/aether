"""spec 0003 2.1, AR-12, R-2: `McpToolGateway` — runtime 의 `ToolGateway` 를
`aether_mcp` 의 **inbound 포트 타입**(`CallTool`·`DiscoverTools`)으로만 구현합니다.

이 파일은 `aether_mcp.application.usecases`·`aether_mcp.adapters` 를 import 하지
않습니다 — fake `CallTool`/`DiscoverTools` 만 씁니다. 예외 변환(`ToolCallDenied`·
`ToolCallFailed`·`ToolNotFound`)이 이 어댑터의 핵심 계약입니다.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID, uuid4

import pytest
from aether_mcp.domain.errors import ToolCallDenied as McpToolCallDenied
from aether_mcp.domain.errors import ToolCallFailed as McpToolCallFailed
from aether_mcp.domain.errors import ToolNotFound as McpToolNotFound
from aether_mcp.domain.tools import McpServerRef, Tool, ToolCall, ToolResult
from aether_runtime.adapters.outbound.tool_gateway.mcp import McpToolGateway
from aether_runtime.application.ports.outbound.tool_gateway import (
    ToolCallDenied,
    ToolCallFailed,
    ToolNotFound,
)

_SERVER = McpServerRef(name="builtin", transport="stdio", command="python", args=("x.py",))


@dataclass
class _FakeCallTool:
    outcome: ToolResult | Exception
    calls: list[ToolCall] = field(default_factory=list)

    def __call__(self, call: ToolCall) -> ToolResult:
        self.calls.append(call)
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return self.outcome


@dataclass
class _FakeDiscoverTools:
    tools: tuple[Tool, ...]

    def __call__(self, server: McpServerRef) -> tuple[Tool, ...]:
        return self.tools


def _gateway(
    *, call_tool: _FakeCallTool | None = None, discover_tools: _FakeDiscoverTools | None = None
) -> McpToolGateway:
    return McpToolGateway(
        call_tool=call_tool or _FakeCallTool(outcome=ToolResult(content="ok")),
        discover_tools=discover_tools or _FakeDiscoverTools(tools=()),
        server=_SERVER,
    )


def test_discover_maps_mcp_tools_to_runtime_tool_schema() -> None:
    tools = (Tool(name="clock", description="tells time", input_schema={"type": "object"}),)
    gateway = _gateway(discover_tools=_FakeDiscoverTools(tools=tools))

    schemas = gateway.discover()

    assert len(schemas) == 1
    assert schemas[0].name == "clock"
    assert schemas[0].description == "tells time"
    assert schemas[0].input_schema == {"type": "object"}


def test_call_forwards_run_and_agent_version_ids_and_maps_result() -> None:
    call_tool = _FakeCallTool(outcome=ToolResult(content="4"))
    gateway = _gateway(call_tool=call_tool)
    run_id: UUID = uuid4()
    agent_version_id: UUID = uuid4()

    result = gateway.call(run_id, agent_version_id, "calculator", {"expression": "2+2"})

    assert result.content == "4"
    assert result.is_error is False
    assert len(call_tool.calls) == 1
    forwarded = call_tool.calls[0]
    assert forwarded.run_id == run_id
    assert forwarded.agent_version_id == agent_version_id
    assert forwarded.server is _SERVER
    assert forwarded.tool_name == "calculator"
    assert forwarded.arguments == {"expression": "2+2"}


def test_call_translates_mcp_denied_to_runtime_denied() -> None:
    gateway = _gateway(call_tool=_FakeCallTool(outcome=McpToolCallDenied("denied")))

    with pytest.raises(ToolCallDenied):
        gateway.call(uuid4(), uuid4(), "calculator", {})


def test_call_translates_mcp_not_found_to_runtime_not_found() -> None:
    gateway = _gateway(call_tool=_FakeCallTool(outcome=McpToolNotFound("nope")))

    with pytest.raises(ToolNotFound):
        gateway.call(uuid4(), uuid4(), "search", {})


def test_call_translates_mcp_failed_to_runtime_failed() -> None:
    gateway = _gateway(call_tool=_FakeCallTool(outcome=McpToolCallFailed("boom")))

    with pytest.raises(ToolCallFailed):
        gateway.call(uuid4(), uuid4(), "calculator", {})


def test_call_does_not_leak_other_exception_types() -> None:
    """AR-12: 변환하지 않은 예외(예: `TypeError`)는 그대로 전파되어 원인이 보입니다."""

    class _Boom(RuntimeError):
        pass

    gateway = _gateway(call_tool=_FakeCallTool(outcome=_Boom("unexpected")))

    with pytest.raises(_Boom):
        gateway.call(uuid4(), uuid4(), "calculator", {})
