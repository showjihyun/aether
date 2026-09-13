"""spec 0002 2.6, D-5: `clock` 도구 — 현재 시각을 `Clock` 포트를 통해 얻으므로 결정적입니다.

`Clock.now()` 가 유일한 시간 출처입니다(AR-9, R-11) — `datetime.now()` 를 직접
부르지 않습니다.
"""

from __future__ import annotations

from typing import Any

from aether_runtime.application.ports.outbound.clock import Clock
from aether_runtime.domain.tools import ToolResult

NAME = "clock"


class ClockTool:
    """`Tool` 포트 구현 — 인자를 받지 않고 `Clock.now()` 를 ISO-8601 문자열로 돌려줍니다."""

    name = NAME
    description = "Returns the current time (ISO-8601, UTC)."
    input_schema: dict[str, Any] = {
        "type": "object",
        "properties": {},
        "additionalProperties": False,
    }

    def __init__(self, clock: Clock) -> None:
        self._clock = clock

    def run(self, arguments: dict[str, Any]) -> ToolResult:
        return ToolResult(content=self._clock.now().isoformat())
