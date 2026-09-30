"""spec 0003 2.3, D-7: 저장소 안 PostgreSQL MCP Server(`tools/mcp-servers/postgres-readonly`)
— Discovery 와 쓰기 구문 거부(화이트리스트)가 DB 연결 없이도 성립하는지 확인합니다.
화이트리스트 위반은 `psycopg.connect` 를 부르기 **전**에 걸러지므로, 이 테스트는
`AETHER_POSTGRES_READONLY_URL` 도 실제 PostgreSQL 도 필요 없습니다 — `--disable-socket`
아래에서도 stdio 서브프로세스로 통과합니다(P2-1 실측과 같은 근거).

읽기 성공 경로(R-8 절반)는 실제 PostgreSQL 이 필요하므로
`test_postgres_readonly_mcp_server_integration.py`(`api-integration`)로 분리했습니다.
"""

from __future__ import annotations

import sys
from pathlib import Path

from aether_mcp.adapters.outbound.mcp_client.stdio import StdioMcpClient
from aether_mcp.domain.tools import McpServerRef

REPO_ROOT = Path(__file__).resolve().parents[3]
POSTGRES_READONLY_SERVER = REPO_ROOT / "tools" / "mcp-servers" / "postgres-readonly" / "server.py"


def _ref() -> McpServerRef:
    return McpServerRef(
        name="postgres-readonly",
        transport="stdio",
        command=sys.executable,
        args=(str(POSTGRES_READONLY_SERVER),),
    )


def test_discover_returns_a_single_query_tool_with_schema() -> None:
    client = StdioMcpClient()

    tools = client.discover(_ref())

    names = {tool.name for tool in tools}
    assert names == {"query"}
    (tool,) = tools
    assert tool.input_schema.get("type") == "object"


def test_call_query_rejects_a_write_statement_without_connecting_to_a_database() -> None:
    """D-7: 읽기 전용을 코드로 보장합니다 — 쓰기 구문은 실행 전에 거부됩니다."""
    client = StdioMcpClient()

    result = client.call(_ref(), "query", {"sql": "DROP TABLE agents"})

    assert result.is_error is True


def test_call_query_rejects_insert() -> None:
    client = StdioMcpClient()

    result = client.call(_ref(), "query", {"sql": "INSERT INTO agents (name) VALUES ('x')"})

    assert result.is_error is True


def test_call_query_rejects_stacked_statements() -> None:
    """화이트리스트를 SELECT 접두사로만 우회하는 것(문장 이어붙이기)을 막습니다."""
    client = StdioMcpClient()

    result = client.call(_ref(), "query", {"sql": "SELECT 1; DROP TABLE agents"})

    assert result.is_error is True
