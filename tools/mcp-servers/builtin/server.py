#!/usr/bin/env python3
"""spec 0003 2.3, D-5: 저장소 안 MCP Server — Phase 1 의 내부 도구 둘(`clock`·
`calculator`)을 그대로 옮깁니다. `packages/mcp`·`tools/mcp-servers/echo` 와 같은
SDK(`mcp` 2.2.0)의 서버 API 로 만든 파이썬 서버입니다.

`calculator` 는 `eval` 을 쓰지 않습니다 — `ast.parse(mode="eval")` 로 구문 트리를
얻고, 허용한 노드 종류(사칙연산·거듭제곱·단항 부호·괄호)만 직접 평가합니다. 이름·
호출·속성 접근 등 그 외 노드는 전부 거부되어 오류 문자열을 돌려줍니다 —
`__import__('os')` 같은 입력이 통과할 길이 애초에 없습니다.

`clock` 은 `datetime.now(UTC)` 를 직접 씁니다 — 이 서버는 별도 프로세스이므로
runtime 의 `Clock` 포트(결정론 목적)를 공유할 수 없습니다. 도구 자체가 "지금"을
묻는 것이 목적이므로 이것이 이 도구의 정의입니다.

stdio 로 직접 실행:  ``python tools/mcp-servers/builtin/server.py``
streamable HTTP 로 실행: ``python tools/mcp-servers/builtin/server.py --http --port 8766``
"""

from __future__ import annotations

import argparse
import ast
import operator
from collections.abc import Callable
from datetime import UTC, datetime

from mcp.server.mcpserver import MCPServer

server = MCPServer("aether-builtin")

Number = int | float

_BIN_OPS: dict[type[ast.operator], Callable[[Number, Number], Number]] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
}

_UNARY_OPS: dict[type[ast.unaryop], Callable[[Number], Number]] = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}


class _CalculatorError(ValueError):
    """지원하지 않는 노드·연산자·값."""


def _evaluate(node: ast.AST) -> Number:
    if isinstance(node, ast.Expression):
        return _evaluate(node.body)
    if isinstance(node, ast.Constant):
        if isinstance(node.value, bool) or not isinstance(node.value, int | float):
            raise _CalculatorError(f"unsupported constant: {node.value!r}")
        return node.value
    if isinstance(node, ast.BinOp):
        op = _BIN_OPS.get(type(node.op))
        if op is None:
            raise _CalculatorError(f"unsupported operator: {type(node.op).__name__}")
        return op(_evaluate(node.left), _evaluate(node.right))
    if isinstance(node, ast.UnaryOp):
        unary_op = _UNARY_OPS.get(type(node.op))
        if unary_op is None:
            raise _CalculatorError(f"unsupported unary operator: {type(node.op).__name__}")
        return unary_op(_evaluate(node.operand))
    raise _CalculatorError(f"unsupported expression: {type(node).__name__}")


@server.tool()
def clock() -> str:
    """현재 시각을 ISO-8601(UTC)로 돌려줍니다."""
    return datetime.now(UTC).isoformat()


@server.tool()
def calculator(expression: str) -> str:
    """사칙연산과 괄호(그리고 거듭제곱 `**`)만 받는 안전한 계산기.

    지원하지 않는 입력은 **예외를 던집니다** — Phase 1 의 `ToolResult(is_error=True)`
    와 같은 신호를 MCP 프로토콜 층에서 그대로 재현하기 위해서입니다(echo 서버의
    `fail` 도구와 같은 패턴, D-5)."""
    try:
        tree = ast.parse(expression, mode="eval")
        value = _evaluate(tree)
    except (SyntaxError, _CalculatorError, ZeroDivisionError, OverflowError) as exc:
        raise ValueError(f"calculator: invalid expression ({exc})") from exc
    return str(value)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--http", action="store_true", help="streamable HTTP 로 실행합니다")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8766)
    args = parser.parse_args()

    if args.http:
        server.run(transport="streamable-http", host=args.host, port=args.port)
    else:
        server.run()


if __name__ == "__main__":
    main()
