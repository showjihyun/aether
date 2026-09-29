"""spec 0003 R-8(절반), D-7: 저장소 안 PostgreSQL MCP Server 가 실제 PostgreSQL 에
Discovery + 호출 1회로 붙는지 확인합니다. HTTP 서버(Fetch)를 통한 R-8 나머지 절반은
2단계(`.importlinter` AR-6 예외 한 줄이 더 필요, spec 2.9 개정 5)로 이월합니다.

`tests.support.pg` 의 세션 컨테이너(`admin_database_url`)를 재사용합니다 —
`AETHER_POSTGRES_READONLY_URL` 은 이 서버 자체의 자격증명이므로(R-11), 여기서는
테스트용 관리자 URL 을 그 값으로 씁니다(실제 배포에서는 read-only 조회 전용
역할을 쓰는 것이 맞지만, 그 역할 설계는 Phase 9 의 Policy Engine 세분화 범위입니다
— 지금은 화이트리스트 + 읽기 전용 트랜잭션이 방어선입니다, D-7).
"""

from __future__ import annotations

import sys
from collections.abc import Callable
from pathlib import Path

import psycopg
import pytest
from aether_mcp.adapters.outbound.mcp_client.stdio import StdioMcpClient
from aether_mcp.domain.tools import McpServerRef

pytestmark = pytest.mark.integration

REPO_ROOT = Path(__file__).resolve().parents[3]
POSTGRES_READONLY_SERVER = REPO_ROOT / "tools" / "mcp-servers" / "postgres-readonly" / "server.py"


def _ref(connection_url: str) -> McpServerRef:
    return McpServerRef(
        name="postgres-readonly",
        transport="stdio",
        command=sys.executable,
        args=(str(POSTGRES_READONLY_SERVER),),
        env={"AETHER_POSTGRES_READONLY_URL": connection_url},
    )


def test_discover_and_call_query_against_real_postgres(
    admin_connection_factory: Callable[[], psycopg.Connection], admin_database_url: str
) -> None:
    conn = admin_connection_factory()
    try:
        with conn.cursor() as cur:
            cur.execute("CREATE TABLE IF NOT EXISTS mcp_readonly_probe (id int, label text)")
            cur.execute("DELETE FROM mcp_readonly_probe")
            cur.execute("INSERT INTO mcp_readonly_probe (id, label) VALUES (1, 'aether')")
        conn.commit()
    finally:
        conn.close()

    # psycopg 는 `postgresql://` URL 을 그대로 받으므로 `+psycopg`(SQLAlchemy 표기)만 벗깁니다
    # (`apps/api/src/aether_api/settings.py::psycopg_dsn` 과 같은 변환).
    connection_url = admin_database_url.replace("postgresql+psycopg://", "postgresql://", 1)
    client = StdioMcpClient()
    ref = _ref(connection_url)

    tools = client.discover(ref)
    assert {tool.name for tool in tools} == {"query"}

    result = client.call(
        ref, "query", {"sql": "SELECT id, label FROM mcp_readonly_probe ORDER BY id"}
    )

    assert result.is_error is False
    assert "aether" in result.content
