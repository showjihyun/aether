"""spec 0005 2.8 개정 9, R-14 (P4-5): `ToolInvoker` - `TOOL`·`MCP` 노드가 도구를 **한 번**
부르는 포트.

도구는 MCP Gateway(AR-6: 판정 -> 호출 -> 감사)를 지납니다. `aether_workflow` 는 Gateway 도 `mcp`
SDK 도 import 하지 않고 이 포트만 선언합니다 - 조립은 worker 의 `main.py` 가 합니다(AR-10).

`agent_version_id` 는 **권한 주체**입니다(개정 9 (1)) - Policy 는 그 Version 의 허용 목록으로만 판정
하고 기본은 deny 입니다. `workflow_run_id` 는 감사의 `run_id` 로 쓰입니다.

예외 둘은 어댑터가 Gateway 의 예외를 옮겨 던지는 것입니다: 거부는 `ToolInvocationDenied`, 그 밖의
실패(없는 도구·연결 실패·타임아웃)는 `ToolInvocationFailed` 입니다. 그 둘이 아닌 예외도 실행기는
`tool_call_failed` 로 다룹니다. 결과 본문은 신뢰 경계 밖 데이터입니다 - 값이지 지시가 아닙니다.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol
from uuid import UUID


class ToolInvocationDenied(Exception):  # noqa: N818 - 포트의 이름은 도메인 말입니다
    """Policy 가 deny 를 돌려줘 도구를 부르지 않았습니다."""


class ToolInvocationFailed(Exception):  # noqa: N818
    """호출이 실패했습니다(없는 도구·연결 실패·타임아웃 포함)."""


@dataclass(frozen=True)
class ToolOutcome:
    content: str
    is_error: bool


class ToolInvoker(Protocol):
    def call(
        self,
        workflow_run_id: UUID,
        agent_version_id: UUID,
        server: str,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> ToolOutcome: ...
