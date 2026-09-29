"""spec 0003 2.1, 2.5, 2.6, AR-12, R-2, R-9 (P2-6): `McpToolGateway` — runtime 의
`ToolGateway` 를 `aether_mcp` 의 **inbound 포트 타입**(`CallTool`·`DiscoverTools`)
으로만 구현합니다.

이 파일은 `aether_mcp.application.usecases`·`aether_mcp.adapters` 를 import 하지
않습니다 — fake `CallTool`/`DiscoverTools` 만 씁니다. 예외 변환(`ToolCallDenied`·
`ToolCallFailed`·`ToolNotFound`)과, P2-6 이 더하는 다중 서버 바인딩 라우팅
(`bind()` 로 정해진 서버 집합만 `discover()`·`call()` 대상)이 이 어댑터의 핵심
계약입니다.
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
from aether_runtime.domain.agent import McpServerBinding

_SERVER = McpServerRef(name="builtin", transport="stdio", command="python", args=("x.py",))
_SECOND_SERVER = McpServerRef(
    name="filesystem", transport="stdio", command="python", args=("y.py",)
)

_BUILTIN_BINDING = McpServerBinding(name="builtin", transport="stdio", ref="builtin")
_FILESYSTEM_BINDING = McpServerBinding(name="filesystem", transport="stdio", ref="filesystem")


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
    """서버 이름 -> 도구 매핑. `raises` 에 있는 이름을 부르면 예외를 올립니다(연결
    실패 흉내, spec 2.5)."""

    by_server: dict[str, tuple[Tool, ...]]
    raises: frozenset[str] = frozenset()
    calls: list[str] = field(default_factory=list)

    def __call__(self, server: McpServerRef) -> tuple[Tool, ...]:
        self.calls.append(server.name)
        if server.name in self.raises:
            raise ConnectionError(f"{server.name} unreachable")
        return self.by_server.get(server.name, ())


def _gateway(
    *,
    call_tool: _FakeCallTool | None = None,
    discover_tools: _FakeDiscoverTools | None = None,
    server_table: dict[str, McpServerRef] | None = None,
) -> McpToolGateway:
    return McpToolGateway(
        call_tool=call_tool or _FakeCallTool(outcome=ToolResult(content="ok")),
        discover_tools=discover_tools or _FakeDiscoverTools(by_server={"builtin": ()}),
        server_table=server_table if server_table is not None else {"builtin": _SERVER},
    )


def test_discover_maps_mcp_tools_to_runtime_tool_schema() -> None:
    tools = (Tool(name="clock", description="tells time", input_schema={"type": "object"}),)
    gateway = _gateway(discover_tools=_FakeDiscoverTools(by_server={"builtin": tools}))
    gateway.bind((_BUILTIN_BINDING,))

    schemas = gateway.discover()

    assert len(schemas) == 1
    assert schemas[0].name == "clock"
    assert schemas[0].description == "tells time"
    assert schemas[0].input_schema == {"type": "object"}


def test_discover_without_bind_returns_no_tools() -> None:
    """spec 2.5: 바인딩이 비어 있으면(`bind()` 를 부르지 않았거나 빈 튜플) 도구
    없이 실행됩니다."""
    gateway = _gateway(
        discover_tools=_FakeDiscoverTools(
            by_server={"builtin": (Tool(name="clock", description=""),)}
        )
    )

    assert gateway.discover() == ()


def test_discover_only_includes_bound_servers_tools() -> None:
    """spec 0003 R-9: 바인딩되지 않은 서버의 도구는 Discovery 에 나타나지 않습니다."""
    discover_tools = _FakeDiscoverTools(
        by_server={
            "builtin": (Tool(name="calculator", description=""),),
            "filesystem": (Tool(name="read_file", description=""),),
        }
    )
    gateway = _gateway(
        discover_tools=discover_tools,
        server_table={"builtin": _SERVER, "filesystem": _SECOND_SERVER},
    )
    gateway.bind((_BUILTIN_BINDING,))

    schemas = gateway.discover()

    assert {schema.name for schema in schemas} == {"calculator"}
    assert "filesystem" not in discover_tools.calls


def test_discover_merges_tools_across_multiple_bound_servers() -> None:
    discover_tools = _FakeDiscoverTools(
        by_server={
            "builtin": (Tool(name="calculator", description=""),),
            "filesystem": (Tool(name="read_file", description=""),),
        }
    )
    gateway = _gateway(
        discover_tools=discover_tools,
        server_table={"builtin": _SERVER, "filesystem": _SECOND_SERVER},
    )
    gateway.bind((_BUILTIN_BINDING, _FILESYSTEM_BINDING))

    schemas = gateway.discover()

    assert {schema.name for schema in schemas} == {"calculator", "read_file"}


def test_discover_skips_a_server_that_fails_to_connect_but_keeps_others() -> None:
    """spec 2.5: 한 서버가 연결 실패면 그 서버의 도구만 빠지고 나머지는 영향 없습니다."""
    discover_tools = _FakeDiscoverTools(
        by_server={"filesystem": (Tool(name="read_file", description=""),)},
        raises=frozenset({"builtin"}),
    )
    gateway = _gateway(
        discover_tools=discover_tools,
        server_table={"builtin": _SERVER, "filesystem": _SECOND_SERVER},
    )
    gateway.bind((_BUILTIN_BINDING, _FILESYSTEM_BINDING))

    schemas = gateway.discover()

    assert {schema.name for schema in schemas} == {"read_file"}


def test_bind_drops_a_binding_whose_ref_is_not_in_the_server_table() -> None:
    """spec 2.9, 과업 지시 3: 바인딩된 이름이 `AETHER_MCP_SERVERS` 에 없으면(=
    `server_table` 에 없으면) 그 서버는 빠지고 Run 은 계속합니다."""
    gateway = _gateway(
        discover_tools=_FakeDiscoverTools(
            by_server={"builtin": (Tool(name="calculator", description=""),)}
        ),
        server_table={"builtin": _SERVER},
    )
    gateway.bind((_BUILTIN_BINDING, _FILESYSTEM_BINDING))  # filesystem 은 table 에 없음

    schemas = gateway.discover()

    assert {schema.name for schema in schemas} == {"calculator"}


def test_call_forwards_run_and_agent_version_ids_and_maps_result() -> None:
    call_tool = _FakeCallTool(outcome=ToolResult(content="4"))
    gateway = _gateway(
        call_tool=call_tool,
        discover_tools=_FakeDiscoverTools(
            by_server={"builtin": (Tool(name="calculator", description=""),)}
        ),
    )
    gateway.bind((_BUILTIN_BINDING,))
    gateway.discover()
    run_id: UUID = uuid4()
    agent_version_id: UUID = uuid4()

    result = gateway.call(run_id, agent_version_id, "calculator", {"expression": "2+2"})

    assert result.content == "4"
    assert result.is_error is False
    assert len(call_tool.calls) == 1
    forwarded = call_tool.calls[0]
    assert forwarded.run_id == run_id
    assert forwarded.agent_version_id == agent_version_id
    assert forwarded.server == _SERVER
    assert forwarded.tool_name == "calculator"
    assert forwarded.arguments == {"expression": "2+2"}


def test_call_routes_to_the_server_that_discovery_attributed_the_name_to() -> None:
    call_tool = _FakeCallTool(outcome=ToolResult(content="ok"))
    discover_tools = _FakeDiscoverTools(
        by_server={
            "builtin": (Tool(name="calculator", description=""),),
            "filesystem": (Tool(name="read_file", description=""),),
        }
    )
    gateway = _gateway(
        call_tool=call_tool,
        discover_tools=discover_tools,
        server_table={"builtin": _SERVER, "filesystem": _SECOND_SERVER},
    )
    gateway.bind((_BUILTIN_BINDING, _FILESYSTEM_BINDING))
    gateway.discover()

    gateway.call(uuid4(), uuid4(), "read_file", {"path": "/tmp/x"})

    assert call_tool.calls[0].server == _SECOND_SERVER


def test_call_of_unknown_name_is_audited_against_a_sentinel_not_a_real_bound_server() -> None:
    """spec 2.5 (코디네이터 지적 2026-09-28): 없는 도구를 실제 바인딩된 서버로
    라우팅하면 그 서버가 요청받은 적 없는 호출의 감사를 떠안습니다(거짓 귀속) —
    감사는 규제·심사 대상 표면이므로 `server_name` 은 실제 서버 이름과 겹치지
    않는 표지(`(unbound)`)여야 합니다. `CallTool` 은 여전히 불려 감사 1건은
    남습니다(spec 2.5 "그 시도도 감사에 남습니다") — 정책 표에 그 표지에 대한
    허용 행은 있을 수 없으므로(기본값 deny, spec 2.4·D-6) `CallTool` 은 보통
    `ToolCallDenied` 를 올리지만, Executor 관점에서 이것은 '없는 도구'이지
    '거부된 도구'가 아니므로 이 어댑터는 그 예외를 `ToolNotFound` 로 번역합니다."""
    call_tool = _FakeCallTool(outcome=McpToolCallDenied("no permission row for sentinel"))
    gateway = _gateway(
        call_tool=call_tool,
        discover_tools=_FakeDiscoverTools(by_server={"builtin": ()}),
        server_table={"builtin": _SERVER},
    )
    gateway.bind((_BUILTIN_BINDING,))
    gateway.discover()

    with pytest.raises(ToolNotFound):
        gateway.call(uuid4(), uuid4(), "search", {})

    assert len(call_tool.calls) == 1
    forwarded_server = call_tool.calls[0].server
    assert forwarded_server != _SERVER
    assert forwarded_server.name == "(unbound)"


def test_call_with_no_bound_servers_still_produces_one_audited_attempt() -> None:
    """spec 2.5: 바인딩이 비어 있어도 그 시도는 감사에 남습니다 — `CallTool` 을
    부르되(감사가 나오도록) 실제 서버가 아닌 표지로 귀속시킵니다."""
    call_tool = _FakeCallTool(outcome=McpToolCallDenied("no permission row for sentinel"))
    gateway = _gateway(call_tool=call_tool, server_table={})

    with pytest.raises(ToolNotFound):
        gateway.call(uuid4(), uuid4(), "calculator", {})

    assert len(call_tool.calls) == 1
    assert call_tool.calls[0].server.name == "(unbound)"


_CALCULATOR_DISCOVERY = _FakeDiscoverTools(
    by_server={"builtin": (Tool(name="calculator", description=""),)}
)


def test_call_translates_mcp_denied_to_runtime_denied() -> None:
    """이름이 실제로 `discover()` 된 서버에 매핑되어야 `call()` 이 그 서버로
    라우팅합니다 — 표지(`_UNBOUND_SENTINEL`) 경로와 섞이지 않도록 `calculator` 를
    `builtin` 이 내놓는 도구로 등록합니다."""
    gateway = _gateway(
        call_tool=_FakeCallTool(outcome=McpToolCallDenied("denied")),
        discover_tools=_CALCULATOR_DISCOVERY,
    )
    gateway.bind((_BUILTIN_BINDING,))
    gateway.discover()

    with pytest.raises(ToolCallDenied):
        gateway.call(uuid4(), uuid4(), "calculator", {})


def test_call_translates_mcp_not_found_to_runtime_not_found() -> None:
    """`search` 는 `builtin` 이 내놓는 도구 목록에 없지만, `builtin` 은 바인딩된
    실제 서버입니다 — `CallTool`(aether_mcp) 이 그 서버 기준으로 `ToolNotFound` 를
    올리는 정상 경로(표지 경로가 아님)를 확인합니다."""
    gateway = _gateway(
        call_tool=_FakeCallTool(outcome=McpToolNotFound("nope")),
        discover_tools=_CALCULATOR_DISCOVERY,
    )
    gateway.bind((_BUILTIN_BINDING,))
    gateway.discover()

    with pytest.raises(ToolNotFound):
        gateway.call(uuid4(), uuid4(), "calculator", {})


def test_call_translates_mcp_failed_to_runtime_failed() -> None:
    gateway = _gateway(
        call_tool=_FakeCallTool(outcome=McpToolCallFailed("boom")),
        discover_tools=_CALCULATOR_DISCOVERY,
    )
    gateway.bind((_BUILTIN_BINDING,))
    gateway.discover()

    with pytest.raises(ToolCallFailed):
        gateway.call(uuid4(), uuid4(), "calculator", {})


def test_call_does_not_leak_other_exception_types() -> None:
    """AR-12: 변환하지 않은 예외(예: `TypeError`)는 그대로 전파되어 원인이 보입니다."""

    class _Boom(RuntimeError):
        pass

    gateway = _gateway(
        call_tool=_FakeCallTool(outcome=_Boom("unexpected")), discover_tools=_CALCULATOR_DISCOVERY
    )
    gateway.bind((_BUILTIN_BINDING,))
    gateway.discover()

    with pytest.raises(_Boom):
        gateway.call(uuid4(), uuid4(), "calculator", {})


def test_close_is_a_no_op_that_does_not_raise() -> None:
    """spec 2.5: Run 종결마다 불립니다 — `bind()` 없이도 안전해야 합니다."""
    gateway = _gateway()

    gateway.close()

    gateway.bind((_BUILTIN_BINDING,))
    gateway.close()
