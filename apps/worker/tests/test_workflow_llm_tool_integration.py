"""spec 0005 2.8 개정 9, R-14 (P4-5): `LLM`·`TOOL`·`MCP` 노드의 전체 경로 - 실제 PostgreSQL
(`aether_data` 역할) + 실제 Redis + 실제 builtin MCP 서버(stdio 서브프로세스).

구성은 **worker 의 프로덕션 조립**(`_build_production_workflow_handler`)입니다. 손으로 꽂지 않으므로
"통로를 새로 만들지 않았다"(모델은 `ModelGateway`, 도구는 MCP Gateway)가 조립까지 포함해
증명됩니다. 모델은 fake(echo) 어댑터, 도구는 저장소 안 builtin 서버(`calculator`·`clock`)입니다.

증명하는 것 (`START -> LLM -> TOOL -> MCP -> END`):
- 권한을 **명시적으로 allow** 한 Agent Version 이면 END 에 도달하고 노드 출력이 기록된다.
- 그 호출이 `data.tool_call_audit` 에 남는다 - 노드마다 한 건, 판정 `allow`/결과 `ok`, 권한 주체는
  그 Agent Version 이다(R-14).
- allow 가 없으면(기본 deny) `TOOL` 노드가 `tool_call_denied` 로 실패하고 Workflow 가 `failed` 다 -
  `MCP` 노드는 실행되지 않는다. deny 판정도 감사에 남는다.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any
from uuid import UUID, uuid4

import psycopg
import pytest
from aether_worker.application.ports.inbound.handle_workflow_requested import (
    WorkflowRequestedMessage,
)
from aether_worker.main import _build_production_workflow_handler
from aether_worker.settings import Settings
from aether_workflow.domain.node import Edge, Node, NodeKind
from redis import Redis

from tests.support.pg import DATA_PASSWORD, DATA_ROLE
from tests.support.workflow_db import declare_workflow_run, issue_api_key

pytestmark = pytest.mark.integration

_Factory = Callable[[], psycopg.Connection]
_DEFINITION = {
    "schema_version": 1,
    "model": {"id": "fake"},
    "instructions": "x",
    "tools": [],
    "policy": {"timeout_seconds": 120, "max_steps": 8, "model_retries": 0, "tool_retries": 0},
}


def _data_url(db_host_port: tuple[str, int]) -> str:
    host, port = db_host_port
    return f"postgresql+psycopg://{DATA_ROLE}:{DATA_PASSWORD}@{host}:{port}/aether"


class _Env:
    def __init__(self, admin: _Factory, db_host_port: tuple[str, int], redis_client: Redis) -> None:
        self.admin = admin
        self.key = issue_api_key(admin)
        self.agent_id, self.version_id = self._agent()
        self.handler = _build_production_workflow_handler(
            Settings(database_url=_data_url(db_host_port)), redis_client
        )

    def _agent(self) -> tuple[UUID, UUID]:
        conn = self.admin()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO control.agents (name) VALUES (%s) RETURNING id",
                    (f"llm-tool-{uuid4()}",),
                )
                row = cur.fetchone()
                assert row is not None
                agent_id: UUID = row[0]
                cur.execute(
                    "INSERT INTO control.agent_versions (agent_id, version, definition)"
                    " VALUES (%s, 1, %s) RETURNING id",
                    (agent_id, json.dumps(_DEFINITION)),
                )
                version = cur.fetchone()
                assert version is not None
            conn.commit()
        finally:
            conn.close()
        return agent_id, version[0]

    def allow(self, server: str, tool: str) -> None:
        conn = self.admin()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO control.tool_permissions"
                    " (agent_version_id, server_name, tool_name, decision)"
                    " VALUES (%s, %s, %s, 'allow')",
                    (self.version_id, server, tool),
                )
            conn.commit()
        finally:
            conn.close()

    def run(self, *, input: dict[str, Any] | None = None) -> UUID:
        nodes = (
            Node("start", NodeKind.START),
            Node("ask", NodeKind.LLM, llm_prompt="summarize:", llm_prompt_path="input.doc"),
            Node(
                "calc",
                NodeKind.TOOL,
                agent_id=self.agent_id,
                tool_server="builtin",
                tool_name="calculator",
                tool_arguments={"expression": "2+2"},
            ),
            Node(
                "now",
                NodeKind.MCP,
                agent_id=self.agent_id,
                tool_server="builtin",
                tool_name="clock",
            ),
            Node("end", NodeKind.END),
        )
        edges = (Edge("start", "ask"), Edge("ask", "calc"), Edge("calc", "now"), Edge("now", "end"))
        run_id, version_id = declare_workflow_run(
            self.admin, nodes, edges, input=input, requested_by=self.key
        )
        self.handler(WorkflowRequestedMessage("0-1", run_id, version_id, None))
        return run_id

    def query(self, sql: str, params: tuple[Any, ...]) -> list[tuple[Any, ...]]:
        conn = self.admin()
        try:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                return cur.fetchall()
        finally:
            conn.close()

    def status(self, run_id: UUID) -> tuple[str, str | None]:
        ((status, reason),) = self.query(
            "SELECT status, failure_reason FROM data.workflow_run_executions"
            " WHERE workflow_run_id = %s",
            (run_id,),
        )
        return str(status), reason

    def nodes(self, run_id: UUID) -> dict[str, tuple[str, str | None, Any]]:
        rows = self.query(
            "SELECT node_id, status, failure_reason, output"
            " FROM data.workflow_node_executions WHERE workflow_run_id = %s",
            (run_id,),
        )
        return {node_id: (status, reason, output) for node_id, status, reason, output in rows}

    def audit(self, run_id: UUID) -> list[tuple[Any, ...]]:
        return self.query(
            "SELECT tool_name, server_name, decision, outcome, agent_version_id, run_kind, run_id"
            " FROM data.tool_call_audit WHERE run_id = %s ORDER BY started_at",
            (run_id,),
        )


@pytest.fixture
def env(
    migrated_database: None,
    admin_connection_factory: _Factory,
    db_host_port: tuple[str, int],
    redis_client: Redis,
) -> _Env:
    return _Env(admin_connection_factory, db_host_port, redis_client)


def test_three_nodes_reach_end_with_their_outputs_recorded(env: _Env) -> None:
    """R-14: 세 노드가 각각 한 번씩 들어간 Workflow 가 END 에 도달하고 출력이 기록된다."""
    env.allow("builtin", "calculator")
    env.allow("builtin", "clock")

    run_id = env.run(input={"doc": "hello"})

    assert env.status(run_id) == ("succeeded", None)
    nodes = env.nodes(run_id)
    assert nodes["ask"][0] == "succeeded"
    assert nodes["ask"][2] == {"text": "summarize:\nhello", "finish_reason": "stop"}
    assert nodes["calc"][2] == {"content": "4", "is_error": False}
    assert nodes["now"][0] == "succeeded"
    assert nodes["now"][2]["is_error"] is False


def test_the_tool_calls_land_in_data_tool_call_audit(env: _Env) -> None:
    """R-14: 도구 호출이 `data.tool_call_audit` 에 남는다 - 노드마다 한 건, 판정 `allow`/결과 `ok`,
    권한 주체는 노드가 지목한 Agent Version, 출처는 `run_kind='workflow'` + Workflow Run id.

    0010 이전에는 `run_id` 의 `control.runs` FK 때문에 이 행들이 **조용히 사라졌다**(감사 쓰기
    실패는 삼켜진다, spec 0003 D-10; 2026-10-17 실측). SQL 로 직접 읽어 단언한다."""
    env.allow("builtin", "calculator")
    env.allow("builtin", "clock")

    run_id = env.run(input={"doc": "hello"})

    assert env.audit(run_id) == [
        ("calculator", "builtin", "allow", "ok", env.version_id, "workflow", run_id),
        ("clock", "builtin", "allow", "ok", env.version_id, "workflow", run_id),
    ]


def test_without_an_allow_the_tool_node_fails_with_tool_call_denied(env: _Env) -> None:
    """기본 deny 의 회귀: 권한이 없으면 `tool_call_denied` 로 노드가 실패한다."""
    run_id = env.run(input={"doc": "hello"})

    assert env.status(run_id) == ("failed", "tool_call_denied")
    nodes = env.nodes(run_id)
    assert nodes["calc"][:2] == ("failed", "tool_call_denied")
    assert "now" not in nodes, "실패한 노드 뒤의 노드는 실행되지 않는다"


def test_a_denial_is_audited_too(env: _Env) -> None:
    """R-14 / spec 0003 D-9: deny 도 감사 1건이다(`denied`) - `workflow` 출처로."""
    run_id = env.run(input={"doc": "hello"})

    assert env.audit(run_id) == [
        ("calculator", "builtin", "deny", "denied", env.version_id, "workflow", run_id)
    ]
