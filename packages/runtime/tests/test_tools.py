"""spec 0002 2.6, D-5: 프로세스 내부 도구 — `clock` 은 `Clock` 포트로 결정적이고,
`calculator` 는 `eval` 없이 사칙연산·괄호·거듭제곱·단항 부호만 평가하며 그 외 입력은
`is_error=True` 입니다. `names()` 는 `BUILTIN_TOOL_NAMES` 와 같아야 합니다(2.1, 2.3).
"""

from __future__ import annotations

from aether_runtime.adapters.outbound.tools.calculator import CalculatorTool
from aether_runtime.adapters.outbound.tools.clock_tool import ClockTool
from aether_runtime.adapters.outbound.tools.registry import InMemoryToolRegistry
from aether_runtime.domain.tools import BUILTIN_TOOL_NAMES

from packages.runtime.tests.fakes import FakeClock


def test_clock_tool_returns_the_clock_ports_current_time() -> None:
    """spec 0002 2.6: `clock` 은 `datetime.now()` 를 직접 부르지 않고 `Clock` 을 통해서만
    시각을 얻으므로 결정적입니다(R-11)."""
    clock = FakeClock()
    tool = ClockTool(clock)

    result = tool.run({})

    assert result.is_error is False
    assert result.content == clock.now().isoformat()


def test_calculator_handles_parentheses_and_precedence() -> None:
    tool = CalculatorTool()

    result = tool.run({"expression": "(1+2)*3"})

    assert result.is_error is False
    assert result.content == "9"


def test_calculator_handles_unary_minus_and_division() -> None:
    tool = CalculatorTool()

    result = tool.run({"expression": "-4/2"})

    assert result.is_error is False
    assert result.content == "-2.0"


def test_calculator_handles_power() -> None:
    tool = CalculatorTool()

    result = tool.run({"expression": "2**10"})

    assert result.is_error is False
    assert result.content == "1024"


def test_calculator_rejects_name_lookup_without_using_eval() -> None:
    """`__import__('os')` 류의 입력은 이름/호출 노드가 허용 목록에 없어 거부됩니다 —
    `eval` 이었다면 실행됐을 것입니다."""
    tool = CalculatorTool()

    result = tool.run({"expression": "__import__('os').getcwd()"})

    assert result.is_error is True


def test_calculator_rejects_bare_name() -> None:
    tool = CalculatorTool()

    result = tool.run({"expression": "os"})

    assert result.is_error is True


def test_calculator_rejects_non_string_expression() -> None:
    tool = CalculatorTool()

    result = tool.run({"expression": 123})

    assert result.is_error is True


def test_calculator_rejects_syntax_errors() -> None:
    tool = CalculatorTool()

    result = tool.run({"expression": "1 +"})

    assert result.is_error is True


def test_registry_names_match_builtin_tool_names() -> None:
    """spec 0002 2.1, 2.3: `BUILTIN_TOOL_NAMES` 는 api 가 `definition.tools` 를 검증할
    때 쓰는 유일한 근거이므로, 레지스트리의 실제 도구 이름과 반드시 같아야 합니다."""
    registry = InMemoryToolRegistry(FakeClock())

    assert registry.names() == BUILTIN_TOOL_NAMES


def test_registry_get_unknown_tool_raises_key_error() -> None:
    registry = InMemoryToolRegistry(FakeClock())

    try:
        registry.get("does-not-exist")
    except KeyError:
        return
    raise AssertionError("expected KeyError")
