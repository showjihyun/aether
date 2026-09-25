"""spec 0003 2.2, D-1: `McpClient` outbound 포트.

`aether_mcp.application` 이 바깥(SDK)에 요구하는 계약입니다. SDK 타입은 이 포트
밖으로 새지 않습니다 — 어댑터가 SDK 결과를 `Tool`·`ToolResult` 로 변환해 돌려줍니다.
"""

from __future__ import annotations

from typing import Any, Protocol

from aether_mcp.domain.tools import McpServerRef, Tool, ToolResult


class McpClient(Protocol):
    def discover(self, server: McpServerRef) -> tuple[Tool, ...]:
        """`server` 에 붙어 도구 목록과 입력 스키마를 돌려줍니다(R-1)."""
        ...

    def call(self, server: McpServerRef, tool_name: str, arguments: dict[str, Any]) -> ToolResult:
        """`server` 의 `tool_name` 을 `arguments` 로 호출합니다.

        도구 쪽 실패는 예외가 아니라 `ToolResult(is_error=True)` 로 돌아옵니다 —
        서버가 살아 있고 프로토콜이 정상인데 도구 실행만 실패한 경우입니다.
        연결 자체가 안 되거나 프로토콜 오류면 예외를 던집니다.
        """
        ...
