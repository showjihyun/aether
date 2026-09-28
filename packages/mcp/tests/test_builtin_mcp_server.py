"""spec 0003 2.3, D-5, R-6: 저장소 안 builtin 서버(`clock`·`calculator`)가 실제
`StdioMcpClient` 로 Discovery·호출되는지 확인합니다 — Phase 1 의 두 도구가 Gateway
경유로 동작함을 증명하는 판정입니다. `--disable-socket` 아래에서도 stdio 서브프로세스는
통과합니다(P2-1 실측과 같은 근거, test_stdio_mcp_client.py 참조).
"""

from __future__ import annotations

import sys
from pathlib import Path

from aether_mcp.adapters.outbound.mcp_client.stdio import StdioMcpClient
from aether_mcp.domain.tools import McpServerRef

REPO_ROOT = Path(__file__).resolve().parents[3]
BUILTIN_SERVER = REPO_ROOT / "tools" / "mcp-servers" / "builtin" / "server.py"


def _builtin_ref() -> McpServerRef:
    return McpServerRef(
        name="builtin", transport="stdio", command=sys.executable, args=(str(BUILTIN_SERVER),)
    )


def test_discover_returns_clock_and_calculator_with_schema() -> None:
    client = StdioMcpClient()

    tools = client.discover(_builtin_ref())

    names = {tool.name for tool in tools}
    assert names == {"clock", "calculator"}
    for tool in tools:
        assert tool.input_schema.get("type") == "object"


def test_call_clock_returns_iso8601_result() -> None:
    client = StdioMcpClient()

    result = client.call(_builtin_ref(), "clock", {})

    assert result.is_error is False
    assert "T" in result.content


def test_call_calculator_handles_parentheses_and_power() -> None:
    client = StdioMcpClient()

    result = client.call(_builtin_ref(), "calculator", {"expression": "(1+2)*2**3"})

    assert result.is_error is False
    assert result.content == "24"


def test_call_calculator_rejects_name_lookup_without_using_eval() -> None:
    """`__import__('os')` 류의 입력은 이름/호출 노드가 허용 목록에 없어 거부됩니다 —
    `eval` 이었다면 실행됐을 것입니다. Phase 1 과 같은 신호(`is_error=True`)가
    MCP 프로토콜 층(예외)을 통해 재현됩니다(D-5)."""
    client = StdioMcpClient()

    result = client.call(_builtin_ref(), "calculator", {"expression": "__import__('os').getcwd()"})

    assert result.is_error is True


def test_call_calculator_rejects_syntax_errors() -> None:
    client = StdioMcpClient()

    result = client.call(_builtin_ref(), "calculator", {"expression": "1 +"})

    assert result.is_error is True
