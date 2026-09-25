"""spec 0003 2.2, 2.3, R-1: MCP 도메인 값 타입 — `Tool`·`ToolResult`·`McpServerRef`.

이 모듈은 표준 라이브러리만 씁니다(AR-9). `mcp` SDK 의 타입은 여기로도,
`application` 으로도 새지 않습니다 — SDK 타입 ↔ 이 타입의 변환은
`adapters/outbound/mcp_client/*` 가 맡습니다(AR-6).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

Transport = Literal["stdio", "http"]


@dataclass(frozen=True)
class McpServerRef:
    """MCP Server 하나를 가리키는 참조.

    `transport` 에 따라 `command`/`args`/`env`(stdio) 또는 `url`(http) 만 채웁니다.
    실제 명령·URL 을 배포 설정(`AETHER_MCP_SERVERS`, spec 2.9)에서 푸는 일은 이
    단위의 범위 밖입니다(P2-6) — 여기서는 이미 풀린 값을 담는 그릇입니다.
    """

    name: str
    transport: Transport
    command: str | None = None
    args: tuple[str, ...] = ()
    env: dict[str, str] | None = None
    url: str | None = None

    def __post_init__(self) -> None:
        if self.transport == "stdio" and not self.command:
            raise ValueError("stdio McpServerRef requires command")
        if self.transport == "http" and not self.url:
            raise ValueError("http McpServerRef requires url")


@dataclass(frozen=True)
class Tool:
    """Discovery 가 돌려주는 도구 하나. MCP `tools/list` 의 항목과 같은 모양입니다."""

    name: str
    description: str
    input_schema: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ToolResult:
    """도구 호출 결과. 신뢰 경계 밖 데이터입니다 — 지시가 아니라 값입니다(R-10)."""

    content: str
    is_error: bool = False
