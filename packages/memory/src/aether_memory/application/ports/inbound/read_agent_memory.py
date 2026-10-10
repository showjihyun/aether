"""spec 0004 2.6, D-8 (P3-4): `ReadAgentMemory` inbound 포트 — Agent 단위로 질의와 가까운
기억을 읽습니다. 돌려주는 것은 검증 전 경험이며, 표지(`verified=false`)는 Context 조립
쪽(`aether_context.domain.memory.render_memory_block`)이 답니다."""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from aether_memory.domain.memory import MemoryHit


class ReadAgentMemory(Protocol):
    def read(self, agent_id: UUID, query: str, *, top_k: int) -> tuple[MemoryHit, ...]:
        """가까운 것이 먼저, 동점은 결정적 순서. 질의가 비었거나 `top_k < 1` 이면 빈 튜플."""
        ...
