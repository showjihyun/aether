"""spec 0004 2.6 (P3-4): `WriteAgentMemory` inbound 포트 — Run 이 종결할 때 Executor 가
**명시적으로 넘긴** 내용을 Agent 의 기억으로 적습니다. 자동 요약·자동 승격은 없습니다."""

from __future__ import annotations

from typing import Protocol
from uuid import UUID


class WriteAgentMemory(Protocol):
    def write(self, agent_id: UUID, run_id: UUID | None, content: str) -> None:
        """`content` 를 그대로 한 건 씁니다. 비어 있으면(공백 포함) 쓰지 않습니다."""
        ...
