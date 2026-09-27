"""spec 0003 R-3, R-4 (이월, plan 0003 리뷰 F-3): Run 경유 판정 — P2-2b 는 Gateway 를
**직접** 3회 불러 감사 3행을 판정했습니다(`packages/mcp/tests/
test_call_tool_gateway_integration.py`). 이 단위(P2-3)는 Run 경로가 처음으로
Gateway 를 지나므로, 여기서 "Run 경유" 판정을 완성합니다.

`ExecuteRunUseCase` 를 실제 `McpToolGateway`(runtime 어댑터) + 실제 `CallToolUseCase`
(mcp) + 실제 `JudgeToolCallUseCase`/`PostgresPermissionTable`(policy) + 실제
`PostgresAuditSink`(mcp) 로 조립합니다. `McpClient` 만 fake 입니다 — P2-1 이 이미
그 계약을 판정했으므로(P2-2b 와 같은 경계 판단).

- R-3: 도구를 3회 부르는 Run 하나 → `data.tool_call_audit` 3행.
- R-4: 정책 표에 deny 를 넣은 Run → `failed` + 사유 `tool_denied`.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

import psycopg
import pytest
from aether_mcp.adapters.outbound.audit_sink.postgres import PostgresAuditSink
from aether_mcp.application.usecases.call_tool import CallToolUseCase
from aether_mcp.application.usecases.discover_tools import DiscoverToolsUseCase
from aether_mcp.domain.tools import McpServerRef
from aether_mcp.domain.tools import Tool as McpTool
from aether_mcp.domain.tools import ToolResult as McpToolResult
from aether_policy.adapters.outbound.permission_table.postgres import PostgresPermissionTable
from aether_policy.application.usecases.judge_tool_call import JudgeToolCallUseCase
from aether_runtime.adapters.outbound.model_gateway.fake import FakeModelGateway
from aether_runtime.adapters.outbound.tool_gateway.mcp import McpToolGateway
from aether_runtime.application.ports.outbound.model_gateway import ModelResponse
from aether_runtime.application.ports.outbound.run_declaration_reader import RunDeclaration
from aether_runtime.application.usecases.execute_run import ExecuteRunUseCase
from aether_runtime.domain.failure import FailureReason
from aether_runtime.domain.run import RunStatus
from aether_runtime.domain.tools import ToolCall

from packages.runtime.tests.fakes import (
    FakeClock,
    FakeEventSink,
    FakeRunDeclarationReader,
    FakeRunStateStore,
    FakeStatusNotifier,
    InMemoryTracer,
)

pytestmark = pytest.mark.integration

_SERVER = McpServerRef(name="echo", transport="stdio", command="python", args=("server.py",))


@dataclass
class _FakeMcpClient:
    """P2-1 이 이미 판정한 `McpClient` 계약의 fake — 이 단위의 판정 대상이 아닙니다."""

    tools: tuple[McpTool, ...]
    calls: list[str] = field(default_factory=list)

    def discover(self, server: McpServerRef) -> tuple[McpTool, ...]:
        del server
        return self.tools

    def call(
        self, server: McpServerRef, tool_name: str, arguments: dict[str, Any]
    ) -> McpToolResult:
        del server, arguments
        self.calls.append(tool_name)
        return McpToolResult(content="ok")


def _insert_agent_version_and_run(conn: psycopg.Connection) -> tuple[UUID, UUID]:
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO control.agents (name) VALUES (%s) RETURNING id",
            (f"agent-{uuid.uuid4()}",),
        )
        row = cur.fetchone()
        assert row is not None
        agent_id = row[0]

        cur.execute(
            """
            INSERT INTO control.agent_versions (agent_id, version, definition)
            VALUES (%s, 1, %s)
            RETURNING id
            """,
            (agent_id, json.dumps({"schema_version": 1})),
        )
        row = cur.fetchone()
        assert row is not None
        version_id: UUID = row[0]

        cur.execute(
            "INSERT INTO control.runs (agent_version_id, input) VALUES (%s, %s) RETURNING id",
            (version_id, "call echo three times"),
        )
        row = cur.fetchone()
        assert row is not None
        run_id: UUID = row[0]
    conn.commit()
    return version_id, run_id


def _insert_permission(
    conn: psycopg.Connection, version_id: UUID, server_name: str, tool_name: str, decision: str
) -> None:
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO control.tool_permissions "
            "(agent_version_id, server_name, tool_name, decision) VALUES (%s, %s, %s, %s)",
            (version_id, server_name, tool_name, decision),
        )
    conn.commit()


def _build_gateway(
    data_connection_factory: Callable[[], psycopg.Connection],
) -> tuple[McpToolGateway, _FakeMcpClient]:
    client = _FakeMcpClient(tools=(McpTool(name="echo", description="echo"),))
    judge = JudgeToolCallUseCase(PostgresPermissionTable(data_connection_factory))
    audit = PostgresAuditSink(data_connection_factory)
    call_tool = CallToolUseCase(judge=judge, client=client, audit=audit)
    discover_tools = DiscoverToolsUseCase(client=client)
    gateway = McpToolGateway(call_tool=call_tool, discover_tools=discover_tools, server=_SERVER)
    return gateway, client


def _definition() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "system_prompt": "You are a helper.",
        "tools": ["echo"],
        "policy": {"timeout_seconds": 120, "max_steps": 8, "model_retries": 0, "tool_retries": 0},
    }


def test_run_calling_a_tool_three_times_produces_three_audit_rows(
    admin_connection_factory: Callable[[], psycopg.Connection],
    data_connection_factory: Callable[[], psycopg.Connection],
) -> None:
    """spec 0003 R-3 (이월, plan 0003 리뷰 F-3): 도구를 3회 부르는 Run 하나에서
    `data.tool_call_audit` 3행."""
    admin_conn = admin_connection_factory()
    try:
        version_id, run_id = _insert_agent_version_and_run(admin_conn)
        _insert_permission(admin_conn, version_id, "echo", "echo", "allow")
    finally:
        admin_conn.close()

    gateway, client = _build_gateway(data_connection_factory)
    clock = FakeClock()
    store = FakeRunStateStore(clock)
    reader = FakeRunDeclarationReader(
        {run_id: RunDeclaration(run_id=run_id, agent_version_id=version_id, input="hi")},
        {version_id: _definition()},
    )
    model_gateway = FakeModelGateway(
        [
            ModelResponse(
                tool_calls=[ToolCall(id="call_1", name="echo", arguments={})],
                finish_reason="tool_calls",
            ),
            ModelResponse(
                tool_calls=[ToolCall(id="call_2", name="echo", arguments={})],
                finish_reason="tool_calls",
            ),
            ModelResponse(
                tool_calls=[ToolCall(id="call_3", name="echo", arguments={})],
                finish_reason="tool_calls",
            ),
            ModelResponse(text="done", finish_reason="stop"),
        ]
    )
    usecase = ExecuteRunUseCase(
        store,
        reader,
        model_gateway,
        gateway,
        FakeEventSink(),
        FakeStatusNotifier(),
        InMemoryTracer(),
        clock,
        owner="p2-3-r3-worker",
    )

    status = usecase(run_id)

    assert status == RunStatus.SUCCEEDED
    assert client.calls == ["echo", "echo", "echo"]

    conn = admin_connection_factory()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT decision, outcome FROM data.tool_call_audit WHERE run_id = %s", (run_id,)
            )
            rows = cur.fetchall()
    finally:
        conn.close()

    assert len(rows) == 3
    assert all(row[0] == "allow" and row[1] == "ok" for row in rows)


def test_run_with_denied_tool_permission_fails_with_tool_denied(
    admin_connection_factory: Callable[[], psycopg.Connection],
    data_connection_factory: Callable[[], psycopg.Connection],
) -> None:
    """spec 0003 R-4 (이월, plan 0003 리뷰 F-3): 정책 표에 deny 를 넣은 Run 이
    `failed` 로 끝나고 사유가 `tool_denied`."""
    admin_conn = admin_connection_factory()
    try:
        version_id, run_id = _insert_agent_version_and_run(admin_conn)
        _insert_permission(admin_conn, version_id, "echo", "echo", "deny")
    finally:
        admin_conn.close()

    gateway, client = _build_gateway(data_connection_factory)
    clock = FakeClock()
    store = FakeRunStateStore(clock)
    reader = FakeRunDeclarationReader(
        {run_id: RunDeclaration(run_id=run_id, agent_version_id=version_id, input="hi")},
        {version_id: _definition()},
    )
    model_gateway = FakeModelGateway(
        [
            ModelResponse(
                tool_calls=[ToolCall(id="call_1", name="echo", arguments={})],
                finish_reason="tool_calls",
            )
        ]
    )
    events = FakeEventSink()
    usecase = ExecuteRunUseCase(
        store,
        reader,
        model_gateway,
        gateway,
        events,
        FakeStatusNotifier(),
        InMemoryTracer(),
        clock,
        owner="p2-3-r4-worker",
    )

    status = usecase(run_id)

    assert status == RunStatus.FAILED
    assert client.calls == []  # deny 면 McpClient 를 부르지 않습니다(spec 2.4)
    final_status_events = [e for e in events.published if e.type == "run.status"]
    assert final_status_events[-1].payload["failure_reason"] == FailureReason.TOOL_DENIED.value

    conn = admin_connection_factory()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT decision, outcome FROM data.tool_call_audit WHERE run_id = %s", (run_id,)
            )
            rows = cur.fetchall()
    finally:
        conn.close()

    assert len(rows) == 1
    assert rows[0] == ("deny", "denied")
