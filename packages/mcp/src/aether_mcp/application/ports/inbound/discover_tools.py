"""spec 0003 2.2, R-1: `DiscoverTools` inbound 포트 — Tool Discovery 유스케이스의 계약."""

from __future__ import annotations

from typing import Protocol

from aether_mcp.domain.tools import McpServerRef, Tool


class DiscoverTools(Protocol):
    def __call__(self, server: McpServerRef) -> tuple[Tool, ...]:
        """`server` 가 내놓는 도구 목록을 스키마와 함께 돌려줍니다."""
        ...
