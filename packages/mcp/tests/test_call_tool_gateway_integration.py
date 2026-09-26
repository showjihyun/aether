"""spec 0003 R-3, 2.4, D-9: `CallToolUseCase` 를 **직접** 3회 불러 `data.tool_call_audit`
에 정확히 3행이 남는지 판정합니다.

plan 0003 리뷰 F-3: Run 경유(runtime → mcp) 판정은 P2-3 이후에만 성립합니다 — 이
단위에는 Gateway 를 지나는 Run 경로가 아직 없으므로, Gateway 유스케이스를 직접
불러 감사 표에 실제로 행이 쌓이는지만 봅니다. `PostgresAuditSink` 는 실제
PostgreSQL 구현이고, `McpClient` 만 fake 입니다(McpClient 는 이 단위의 범위가
아니라 P2-1 이 이미 판정했습니다).
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import psycopg
import pytest
from aether_mcp.adapters.outbound.audit_sink.postgres import PostgresAuditSink
from aether_mcp.application.usecases.call_tool import CallToolUseCase
from aether_mcp.domain.tools import McpServerRef, Tool, ToolCall, ToolResult
from aether_policy.domain.decision import Decision

pytestmark = pytest.mark.integration


@dataclass
class FakeMcpClient:
    tools: tuple[Tool, ...]

    def discover(self, server: McpServerRef) -> tuple[Tool, ...]:
        return self.tools

    def call(self, server: McpServerRef, tool_name: str, arguments: dict[str, Any]) -> ToolResult:
        return ToolResult(content="ok")


@dataclass
class AllowJudge:
    calls: list[tuple[uuid.UUID, str, str]] = field(default_factory=list)

    def __call__(self, agent_version_id: uuid.UUID, server_name: str, tool_name: str) -> Decision:
        self.calls.append((agent_version_id, server_name, tool_name))
        return "allow"


def _insert_agent_version_and_run(conn: psycopg.Connection) -> tuple[uuid.UUID, uuid.UUID]:
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
        version_id: uuid.UUID = row[0]

        cur.execute(
            "INSERT INTO control.runs (agent_version_id, input) VALUES (%s, %s) RETURNING id",
            (version_id, "hello"),
        )
        row = cur.fetchone()
        assert row is not None
        run_id: uuid.UUID = row[0]
    conn.commit()
    return version_id, run_id


def test_gateway_called_three_times_produces_three_audit_rows(
    admin_connection_factory: Callable[[], psycopg.Connection],
    data_connection_factory: Callable[[], psycopg.Connection],
) -> None:
    admin_conn = admin_connection_factory()
    try:
        version_id, run_id = _insert_agent_version_and_run(admin_conn)
    finally:
        admin_conn.close()

    server = McpServerRef(name="echo", transport="stdio", command="python", args=("server.py",))
    client = FakeMcpClient(tools=(Tool(name="echo", description=""),))
    audit = PostgresAuditSink(connect=data_connection_factory)
    judge = AllowJudge()
    gateway = CallToolUseCase(judge=judge, client=client, audit=audit)

    for _ in range(3):
        result = gateway(
            ToolCall(
                run_id=run_id,
                agent_version_id=version_id,
                server=server,
                tool_name="echo",
                arguments={},
            )
        )
        assert result.content == "ok"

    conn = admin_connection_factory()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT run_id, decision, outcome FROM data.tool_call_audit WHERE run_id = %s",
                (run_id,),
            )
            rows = cur.fetchall()
    finally:
        conn.close()

    assert len(rows) == 3
    assert all(row[0] == run_id for row in rows)
    assert all(row[1] == "allow" for row in rows)
    assert all(row[2] == "ok" for row in rows)
