#!/usr/bin/env python3
"""spec 0003 2.3, D-7: 저장소 안 PostgreSQL MCP Server — read-only 조회 한 가지.

참조 구현(`@modelcontextprotocol/server-postgres`)이 archive 되어(2026-09-25 확인)
이 저장소가 직접 만듭니다(D-7, C-6). `packages/mcp`·`tools/mcp-servers/echo`·
`tools/mcp-servers/builtin` 과 같은 SDK(`mcp` 2.2.0)의 서버 API 로 만든 파이썬
서버입니다.

도구는 `query` **하나**로 좁힙니다. 읽기 전용을 코드로 이중으로 보장합니다:

1. **화이트리스트**: `SELECT`/`WITH` 로 시작하지 않거나 문장이 둘 이상이면
   DB 에 연결하지도 않고 거부합니다(`_check_read_only`) — 자격증명·DB 가 없어도
   이 경로는 결정적으로 실패합니다.
2. **읽기 전용 트랜잭션**: 화이트리스트를 통과한 뒤에도 `conn.read_only = True`
   로 연결을 읽기 전용 트랜잭션으로 열어(psycopg3) DB 가 두 번째 방어선이 됩니다
   — 예컨대 부작용이 있는 함수를 `SELECT` 로 감싸는 시도까지 막습니다.

자격증명은 환경변수 `AETHER_POSTGRES_READONLY_URL`(libpq 접속 문자열 또는
`postgresql://` URL) **로만** 받습니다(R-11) — 코드·로그에 원문을 남기지 않습니다.

stdio 로 직접 실행(저장소 루트에서)::

    AETHER_POSTGRES_READONLY_URL=... python tools/mcp-servers/postgres-readonly/server.py

streamable HTTP 로 실행하려면 같은 명령에 ``--http --port 8767`` 을 더합니다.
"""

from __future__ import annotations

import argparse
import json
import os
import re

import psycopg
from mcp.server.mcpserver import MCPServer

server = MCPServer("aether-postgres-readonly")

_ENV_VAR = "AETHER_POSTGRES_READONLY_URL"
_MAX_ROWS = 200

# 선행 주석(`--`, `/* ... */`)을 건너뛰고 첫 키워드만 봅니다. 그 키워드가
# `select`/`with` 가 아니면 거부합니다 — `with ... as (...) select ...`(CTE)도
# `with` 로 시작하므로 허용됩니다.
_LEADING_COMMENT_RE = re.compile(r"\A(?:\s+|--[^\n]*\n|/\*.*?\*/)*", re.DOTALL)
_LEADING_KEYWORD_RE = re.compile(r"([A-Za-z_][A-Za-z0-9_]*)")
_ALLOWED_LEADING_KEYWORDS = {"select", "with"}


class ReadOnlyViolation(ValueError):
    """조회(`SELECT`/`WITH`) 이외의 구문, 또는 문장이 둘 이상(spec 2.3, D-7)."""


def _check_read_only(sql_text: str) -> None:
    """DB 에 연결하기 **전에** 화이트리스트로 거부합니다 — 위반이면 `ReadOnlyViolation`."""
    stripped = sql_text.strip()
    if not stripped:
        raise ReadOnlyViolation("query: empty statement")
    # 끝의 세미콜론 하나는 허용하되, 그 앞에 또 다른 세미콜론(문장 이어붙이기)은 거부합니다.
    body = stripped[:-1] if stripped.endswith(";") else stripped
    if ";" in body:
        raise ReadOnlyViolation("query: multiple statements are not allowed")

    leading = _LEADING_COMMENT_RE.match(stripped)
    after_comments = stripped[leading.end() :] if leading else stripped
    match = _LEADING_KEYWORD_RE.match(after_comments)
    keyword = match.group(1).lower() if match else ""
    if keyword not in _ALLOWED_LEADING_KEYWORDS:
        raise ReadOnlyViolation(
            f"query: only SELECT/WITH statements are allowed, got {keyword or stripped[:20]!r}"
        )


def _connection_url() -> str:
    url = os.environ.get(_ENV_VAR)
    if not url:
        raise RuntimeError(f"{_ENV_VAR} is not set")
    return url


@server.tool()
def query(sql: str) -> str:
    """읽기 전용 `SELECT`/`WITH` 문 하나를 실행하고 행을 JSON 문자열로 돌려줍니다.

    쓰기 구문(`INSERT`/`UPDATE`/`DELETE`/DDL 등)과 여러 문장을 이어붙인 입력은
    DB 에 연결하기 전에 거부됩니다(화이트리스트, D-7). 행 수는 최대 200 으로
    자릅니다 — 결과 크기 상한은 Gateway(`AETHER_MCP_MAX_RESULT_BYTES`, spec 2.9)의
    몫이지만, 이 서버 자체도 한 번에 과도한 행을 돌려주지 않습니다."""
    try:
        _check_read_only(sql)
    except ReadOnlyViolation as exc:
        raise ValueError(str(exc)) from exc

    with psycopg.connect(_connection_url()) as conn:
        conn.read_only = True
        with conn.cursor() as cur:
            cur.execute(sql)  # noqa: S608 -- 화이트리스트 + 읽기 전용 트랜잭션 이중 방어(D-7)
            columns = [desc.name for desc in cur.description] if cur.description else []
            rows = cur.fetchmany(_MAX_ROWS)
        conn.rollback()

    return json.dumps(
        [dict(zip(columns, row, strict=True)) for row in rows], default=str, ensure_ascii=False
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--http", action="store_true", help="streamable HTTP 로 실행합니다")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8767)
    args = parser.parse_args()

    if args.http:
        server.run(transport="streamable-http", host=args.host, port=args.port)
    else:
        server.run()


if __name__ == "__main__":
    main()
