"""spec 0002 2.6, D-5: `calculator` 도구 — 사칙연산과 괄호(그리고 거듭제곱 `**`, 완료
판정의 `2**10` 케이스를 만족시키기 위해)만 받는 안전한 파서. **`eval` 을 쓰지
않습니다** — `ast.parse(mode="eval")` 로 구문 트리를 얻고, 허용한 노드 종류만 직접
평가합니다. 이름·호출·속성 접근 등 그 외 노드는 전부 거부되어 `ToolResult(is_error=True)`
가 됩니다 — `__import__('os')` 같은 입력이 통과할 길이 애초에 없습니다(허용 노드
목록에 `ast.Call`/`ast.Name`/`ast.Attribute` 가 없습니다).
"""

from __future__ import annotations

import ast
import operator
from collections.abc import Callable
from typing import Any

from aether_runtime.domain.tools import ToolResult

NAME = "calculator"

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


class CalculatorError(ValueError):
    """지원하지 않는 노드·연산자·값 — `run` 이 `ToolResult(is_error=True)` 로 바꿉니다."""


def _evaluate(node: ast.AST) -> Number:
    if isinstance(node, ast.Expression):
        return _evaluate(node.body)
    if isinstance(node, ast.Constant):
        if isinstance(node.value, bool) or not isinstance(node.value, int | float):
            raise CalculatorError(f"unsupported constant: {node.value!r}")
        return node.value
    if isinstance(node, ast.BinOp):
        op = _BIN_OPS.get(type(node.op))
        if op is None:
            raise CalculatorError(f"unsupported operator: {type(node.op).__name__}")
        return op(_evaluate(node.left), _evaluate(node.right))
    if isinstance(node, ast.UnaryOp):
        unary_op = _UNARY_OPS.get(type(node.op))
        if unary_op is None:
            raise CalculatorError(f"unsupported unary operator: {type(node.op).__name__}")
        return unary_op(_evaluate(node.operand))
    raise CalculatorError(f"unsupported expression: {type(node).__name__}")


class CalculatorTool:
    """`Tool` 포트 구현. 입력은 `{"expression": "<문자열>"}`."""

    name = NAME
    description = "Evaluates an arithmetic expression: numbers, + - * / **, parentheses."
    input_schema: dict[str, Any] = {
        "type": "object",
        "properties": {"expression": {"type": "string"}},
        "required": ["expression"],
        "additionalProperties": False,
    }

    def run(self, arguments: dict[str, Any]) -> ToolResult:
        expression = arguments.get("expression")
        if not isinstance(expression, str):
            return ToolResult(content="calculator: 'expression' must be a string", is_error=True)
        try:
            tree = ast.parse(expression, mode="eval")
            value = _evaluate(tree)
        except (SyntaxError, CalculatorError, ZeroDivisionError, OverflowError) as exc:
            return ToolResult(content=f"calculator: invalid expression ({exc})", is_error=True)
        return ToolResult(content=str(value))
