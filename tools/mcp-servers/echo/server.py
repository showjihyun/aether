#!/usr/bin/env python3
"""spec 0003 2.3, R-1: 저장소 안 테스트용 MCP Server — 도구 `echo` 와 `fail`.

`packages/mcp` 와 같은 SDK(`mcp` 2.2.0)로 만든 파이썬 서버입니다. 새 언어 런타임을
테스트에 들이지 않기 위해서입니다(plan 0003 F-7). `fail` 은 항상 결정적으로
실패해 실패 경로 판정(R-1)의 대상이 됩니다.

stdio 로 직접 실행:  ``python tools/mcp-servers/echo/server.py``
streamable HTTP 로 실행: ``python tools/mcp-servers/echo/server.py --http --port 8765``
"""

from __future__ import annotations

import argparse

from mcp.server.mcpserver import MCPServer

server = MCPServer("aether-echo")


@server.tool()
def echo(text: str) -> str:
    """받은 문자열을 그대로 돌려줍니다."""
    return text


@server.tool()
def fail(reason: str = "boom") -> str:
    """항상 실패합니다 — 실패 경로를 결정적으로 재현하기 위한 도구입니다."""
    raise RuntimeError(reason)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--http", action="store_true", help="streamable HTTP 로 실행합니다")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()

    if args.http:
        server.run(transport="streamable-http", host=args.host, port=args.port)
    else:
        server.run()


if __name__ == "__main__":
    main()
