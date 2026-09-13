"""spec 0002 2.1, 2.6: `InMemoryToolRegistry` — Phase 1 의 프로세스 내부 도구 레지스트리.

`names()` 는 `BUILTIN_TOOL_NAMES`(domain, api 가 `definition.tools` 검증에 쓰는 근거)와
같아야 하고 그것을 단언하는 테스트가 있습니다(plan 0002 P1-4 순서 3). Phase 2 는 이
어댑터를 MCP 클라이언트로 바꾸고 `ToolRegistry` 포트와 유스케이스는 바뀌지 않습니다.
"""

from __future__ import annotations

from aether_runtime.adapters.outbound.tools.calculator import CalculatorTool
from aether_runtime.adapters.outbound.tools.clock_tool import ClockTool
from aether_runtime.application.ports.outbound.clock import Clock
from aether_runtime.application.ports.outbound.tools import Tool


class InMemoryToolRegistry:
    """`ToolRegistry` 포트 구현 — `clock`·`calculator` 를 담습니다."""

    def __init__(self, clock: Clock) -> None:
        self._tools: dict[str, Tool] = {
            ClockTool.name: ClockTool(clock),
            CalculatorTool.name: CalculatorTool(),
        }

    def get(self, name: str) -> Tool:
        return self._tools[name]

    def names(self) -> frozenset[str]:
        return frozenset(self._tools)
