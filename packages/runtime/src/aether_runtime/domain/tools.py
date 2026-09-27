"""spec 0002 2.1, 2.6, D-5: 도구 값 타입 — MCP tool 과 같은 모양입니다.

spec 0003 2.15, D-16(spec 0002 D-3 [실질] 개정): 도구 이름의 생성 시 정적 검증은
없앴습니다 — 도구는 Discovery 에서 오고, api 는 Agent 생성 시점에 어떤 MCP Server 가
붙을지 모릅니다. 그래서 `BUILTIN_TOOL_NAMES` 는 더 이상 없습니다. 없는 도구는 Run
시점에 `ToolGateway.call` 이 `ToolNotFound` 로 실패시키고 감사에 남습니다.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


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
