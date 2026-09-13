"""spec 0002 2.1, 2.6, D-5: `Tool`·`ToolRegistry` — 프로세스 내부 도구도 MCP tool 과
같은 모양입니다(`name`, `description`, `input_schema`, `run -> ToolResult`).

Phase 2 는 이 포트의 구현을 MCP 클라이언트로 바꾸고 유스케이스(`ExecuteRun`)는
바뀌지 않습니다 — 그래서 지금부터 이 모양입니다.
"""

from __future__ import annotations

from typing import Any, Protocol

from aether_runtime.domain.tools import ToolResult


class Tool(Protocol):
    """도구 하나. MCP tool 과 같은 필드(D-5)."""

    name: str
    description: str
    input_schema: dict[str, Any]

    def run(self, arguments: dict[str, Any]) -> ToolResult: ...


class ToolRegistry(Protocol):
    def get(self, name: str) -> Tool:
        """등록되지 않은 이름이면 `KeyError`(spec 2.8 `unknown_tool` 판정의 근거)."""
        ...

    def names(self) -> frozenset[str]: ...
