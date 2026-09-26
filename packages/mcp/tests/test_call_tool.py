"""spec 0003 2.4, D-6, D-9, D-10, D-11, 2.5, D-16, R-3, R-4: `CallToolUseCase` — 판정 →
호출 → 감사의 고정 순서를 fake 협력자로 컨테이너 없이 판정합니다.

진입점은 `CallToolUseCase` 하나입니다 — 이 테스트들도 그 하나만 부릅니다. 타임아웃
강제는 어댑터(`adapters/outbound/mcp_client/{stdio,http}.py`)의 책임이므로 여기서는
`McpClient.call` 이 타임아웃을 흉내 낸 예외(`TimeoutError`)를 올렸을 때 Gateway 가
그것을 다른 실패와 같은 방식으로 감싸는지만 봅니다(실제 시간 강제는
`test_stdio_mcp_client_timeout.py`·`test_http_mcp_client_timeout.py`).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import UUID, uuid4

import pytest
from aether_mcp.application.usecases.call_tool import CallToolUseCase
from aether_mcp.domain.audit import AuditRecord
from aether_mcp.domain.errors import ToolCallDenied, ToolCallFailed, ToolNotFound
from aether_mcp.domain.tools import McpServerRef, Tool, ToolCall, ToolResult
from aether_policy.domain.decision import Decision


@dataclass
class FakeJudge:
    decision: Decision = "allow"
    calls: list[tuple[UUID, str, str]] = field(default_factory=list)

    def __call__(self, agent_version_id: UUID, server_name: str, tool_name: str) -> Decision:
        self.calls.append((agent_version_id, server_name, tool_name))
        return self.decision


@dataclass
class FakeMcpClient:
    tools_by_server: dict[str, tuple[Tool, ...]] = field(default_factory=dict)
    fail_discover_servers: set[str] = field(default_factory=set)
    call_results: dict[str, ToolResult] = field(default_factory=dict)
    call_exceptions: dict[str, Exception] = field(default_factory=dict)
    discover_calls: list[str] = field(default_factory=list)
    call_calls: list[tuple[str, str]] = field(default_factory=list)

    def discover(self, server: McpServerRef) -> tuple[Tool, ...]:
        self.discover_calls.append(server.name)
        if server.name in self.fail_discover_servers:
            raise ConnectionError(f"cannot connect to {server.name}")
        return self.tools_by_server.get(server.name, ())

    def call(self, server: McpServerRef, tool_name: str, arguments: dict[str, Any]) -> ToolResult:
        self.call_calls.append((server.name, tool_name))
        if server.name in self.call_exceptions:
            raise self.call_exceptions[server.name]
        return self.call_results.get(server.name, ToolResult(content="ok"))


@dataclass
class FakeAuditSink:
    records: list[AuditRecord] = field(default_factory=list)
    raise_on_record: bool = False

    def record(self, record: AuditRecord) -> None:
        if self.raise_on_record:
            raise RuntimeError("audit sink down")
        self.records.append(record)


def _server(name: str = "echo") -> McpServerRef:
    return McpServerRef(name=name, transport="stdio", command="python", args=("server.py",))


def _tool_call(
    server: McpServerRef, tool_name: str = "echo", run_id: UUID | None = None
) -> ToolCall:
    return ToolCall(
        run_id=run_id or uuid4(),
        agent_version_id=uuid4(),
        server=server,
        tool_name=tool_name,
        arguments={},
    )


def _gateway(
    judge: FakeJudge, client: FakeMcpClient, audit: FakeAuditSink, **kwargs: Any
) -> CallToolUseCase:
    return CallToolUseCase(judge=judge, client=client, audit=audit, **kwargs)


def test_deny_does_not_call_mcp_client_and_is_audited() -> None:
    """spec R-4: deny 면 `McpClient.call` 이 0회 호출되고 감사 1건, `ToolCallDenied`."""
    server = _server()
    client = FakeMcpClient(tools_by_server={server.name: (Tool(name="echo", description=""),)})
    audit = FakeAuditSink()
    judge = FakeJudge(decision="deny")
    gateway = _gateway(judge, client, audit)
    call = _tool_call(server)

    with pytest.raises(ToolCallDenied):
        gateway(call)

    assert client.call_calls == []
    assert len(audit.records) == 1
    record = audit.records[0]
    assert record.decision == "deny"
    assert record.outcome == "denied"
    assert record.run_id == call.run_id
    assert record.agent_version_id == call.agent_version_id
    assert record.tool_name == call.tool_name


def test_success_failure_denied_each_produce_one_audit_record_matching_call() -> None:
    """spec R-3: 성공·실패·거부 세 경우 각각 감사 1건, 필드가 호출과 일치."""
    ok_server = _server("ok-server")
    fail_server = _server("fail-server")
    deny_server = _server("deny-server")
    client = FakeMcpClient(
        tools_by_server={
            "ok-server": (Tool(name="echo", description=""),),
            "fail-server": (Tool(name="echo", description=""),),
        },
        call_exceptions={"fail-server": ConnectionError("boom")},
    )
    audit = FakeAuditSink()

    judge = FakeJudge(decision="allow")
    gateway = _gateway(judge, client, audit)

    ok_call = _tool_call(ok_server)
    gateway(ok_call)

    fail_call = _tool_call(fail_server)
    with pytest.raises(ToolCallFailed):
        gateway(fail_call)

    judge.decision = "deny"
    deny_call = _tool_call(deny_server)
    with pytest.raises(ToolCallDenied):
        gateway(deny_call)

    assert len(audit.records) == 3
    ok_record, fail_record, deny_record = audit.records

    assert ok_record.outcome == "ok"
    assert ok_record.decision == "allow"
    assert ok_record.run_id == ok_call.run_id
    assert ok_record.server_name == "ok-server"

    assert fail_record.outcome == "error"
    assert fail_record.decision == "allow"
    assert fail_record.run_id == fail_call.run_id
    assert fail_record.error_kind is not None

    assert deny_record.outcome == "denied"
    assert deny_record.decision == "deny"
    assert deny_record.run_id == deny_call.run_id


def test_audit_sink_failure_does_not_change_call_result() -> None:
    """spec D-10: 감사 기록 실패는 호출 결과를 바꾸지 않습니다."""
    server = _server()
    client = FakeMcpClient(
        tools_by_server={server.name: (Tool(name="echo", description=""),)},
        call_results={server.name: ToolResult(content="hello")},
    )
    audit = FakeAuditSink(raise_on_record=True)
    judge = FakeJudge(decision="allow")
    gateway = _gateway(judge, client, audit)

    result = gateway(_tool_call(server))

    assert result == ToolResult(content="hello")


def test_one_server_connection_failure_only_affects_that_server() -> None:
    """spec 2.5: 서버 1개 연결 실패 시 그 서버의 도구만 빠지고 나머지 서버는 정상."""
    broken = _server("broken-server")
    healthy = _server("healthy-server")
    client = FakeMcpClient(
        tools_by_server={"healthy-server": (Tool(name="echo", description=""),)},
        fail_discover_servers={"broken-server"},
    )
    audit = FakeAuditSink()
    judge = FakeJudge(decision="allow")
    gateway = _gateway(judge, client, audit)

    with pytest.raises(ToolNotFound):
        gateway(_tool_call(broken, tool_name="echo"))

    result = gateway(_tool_call(healthy, tool_name="echo"))
    assert result.content == "ok"


def test_unknown_tool_name_raises_tool_not_found_and_is_audited() -> None:
    """spec 2.5, D-16: 없는 도구 이름 -> `ToolNotFound`, 그 시도도 감사에 남음."""
    server = _server()
    client = FakeMcpClient(tools_by_server={server.name: (Tool(name="echo", description=""),)})
    audit = FakeAuditSink()
    judge = FakeJudge(decision="allow")
    gateway = _gateway(judge, client, audit)

    with pytest.raises(ToolNotFound):
        gateway(_tool_call(server, tool_name="does-not-exist"))

    assert client.call_calls == []
    assert len(audit.records) == 1
    assert audit.records[0].outcome == "error"
    assert audit.records[0].error_kind == "tool_not_found"


def test_result_over_cap_is_truncated_but_audit_keeps_original_size() -> None:
    """spec 2.9, D-12: 결과가 상한을 넘으면 잘리고 감사의 `result_bytes` 는 원래 크기."""
    server = _server()
    big_content = "x" * 100
    client = FakeMcpClient(
        tools_by_server={server.name: (Tool(name="echo", description=""),)},
        call_results={server.name: ToolResult(content=big_content)},
    )
    audit = FakeAuditSink()
    judge = FakeJudge(decision="allow")
    gateway = _gateway(judge, client, audit, max_result_bytes=10)

    result = gateway(_tool_call(server))

    assert len(result.content.encode("utf-8")) <= 10
    assert len(audit.records) == 1
    assert audit.records[0].result_bytes == 100


def test_reconnect_is_attempted_at_most_once_per_call() -> None:
    """spec 2.5, D-11: 재연결은 호출당 1회까지 — 무한 재시도 없음."""
    server = _server()
    client = FakeMcpClient(
        tools_by_server={server.name: (Tool(name="echo", description=""),)},
        call_exceptions={server.name: ConnectionError("down")},
    )
    audit = FakeAuditSink()
    judge = FakeJudge(decision="allow")
    gateway = _gateway(judge, client, audit)

    with pytest.raises(ToolCallFailed):
        gateway(_tool_call(server))

    # 최초 시도 + 재연결 1회 = 정확히 2회. 그 이상 반복되지 않습니다.
    assert client.call_calls == [(server.name, "echo"), (server.name, "echo")]


def test_timeout_error_from_client_is_wrapped_and_audited_with_error_kind() -> None:
    """spec 2.9: 어댑터가 타임아웃을 `TimeoutError` 로 올리면(강제는 어댑터 책임),
    Gateway 는 다른 실패와 같은 방식으로 `ToolCallFailed` 로 감싸고 감사의
    `error_kind` 에 그 종류를 남깁니다."""
    server = _server()
    client = FakeMcpClient(
        tools_by_server={server.name: (Tool(name="echo", description=""),)},
        call_exceptions={server.name: TimeoutError("call exceeded AETHER_MCP_CALL_TIMEOUT_MS")},
    )
    audit = FakeAuditSink()
    judge = FakeJudge(decision="allow")
    gateway = _gateway(judge, client, audit)

    with pytest.raises(ToolCallFailed):
        gateway(_tool_call(server))

    assert len(audit.records) == 1
    assert audit.records[0].error_kind == "TimeoutError"
