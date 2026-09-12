"""spec 0002 2.1, 2.6, D-5: 도구 값 타입 — 지금부터 MCP tool 과 같은 모양입니다.

`BUILTIN_TOOL_NAMES` 는 api 가 `definition.tools` 를 검증할 때 쓰는 유일한 근거입니다
— api 는 어댑터(레지스트리)를 모르므로 이 상수로만 검증합니다(2.3).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

BUILTIN_TOOL_NAMES: frozenset[str] = frozenset({"clock", "calculator"})


@dataclass(frozen=True)
class ToolCall:
    """모델 응답이 요청한 도구 호출 하나. `id` 는 `tool` 메시지의 `tool_call_id` 로 되돌아갑니다."""

    id: str
    name: str
    arguments: dict[str, Any]


@dataclass(frozen=True)
class ToolResult:
    """도구 실행 결과. 신뢰 경계 밖 데이터로 다뤄집니다(`Observation`, R-14)."""

    content: str
    is_error: bool = False
