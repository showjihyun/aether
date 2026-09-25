"""spec 0003 R-1, 2.2: `StdioMcpClient` 가 저장소 안 echo 서버(2.3)에 실제로 붙어
Discovery 와 호출 성공·실패 경로를 만족하는지 확인합니다. 프로젝트 전역
`--disable-socket`(pytest-socket) 아래에서 돕니다 — stdio 는 서브프로세스 파이프이지
네트워크 소켓이 아니므로 통과합니다(구현자 보고의 "stdio 실측" 참조).
"""

from __future__ import annotations

import sys
from pathlib import Path

from aether_mcp.adapters.outbound.mcp_client.stdio import StdioMcpClient
from aether_mcp.domain.tools import McpServerRef

REPO_ROOT = Path(__file__).resolve().parents[3]
ECHO_SERVER = REPO_ROOT / "tools" / "mcp-servers" / "echo" / "server.py"


def _echo_ref() -> McpServerRef:
    return McpServerRef(
        name="echo", transport="stdio", command=sys.executable, args=(str(ECHO_SERVER),)
    )


def test_discover_returns_echo_and_fail_with_schema() -> None:
    client = StdioMcpClient()

    tools = client.discover(_echo_ref())

    names = {tool.name for tool in tools}
    assert names == {"echo", "fail"}
    for tool in tools:
        assert tool.input_schema.get("type") == "object"


def test_call_echo_succeeds() -> None:
    client = StdioMcpClient()

    result = client.call(_echo_ref(), "echo", {"text": "hello"})

    assert result.is_error is False
    assert "hello" in result.content


def test_call_fail_returns_error_result() -> None:
    """`fail` 도구는 항상 예외를 던지므로 실패 경로가 결정적으로 재현됩니다."""
    client = StdioMcpClient()

    result = client.call(_echo_ref(), "fail", {"reason": "boom"})

    assert result.is_error is True
