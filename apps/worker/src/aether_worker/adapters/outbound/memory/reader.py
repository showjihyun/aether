"""spec 0004 2.1, 2.6, D-8, AR-3 (P3-4): `MemoryReaderAdapter` — `aether_memory` 의 읽기
유스케이스(`ReadAgentMemory`)를 `aether_context` 의 `MemoryReader` 포트 모양으로 바꿉니다.

`aether_context` 와 `aether_memory` 는 서로를 import 하지 않습니다 — 두 패키지의 값 타입
(`MemoryHit`)이 이름은 같아도 다른 클래스이므로, 조립 지점인 worker 가 변환만 합니다
(`ModelGatewayEmbedder` 와 같은 자리). 순서는 그대로 보존합니다(R-1).
"""

from __future__ import annotations

from uuid import UUID

from aether_context.domain.memory import MemoryHit
from aether_memory.application.ports.inbound.read_agent_memory import ReadAgentMemory


class MemoryReaderAdapter:
    """`aether_context.application.ports.outbound.memory_reader.MemoryReader` 의 구현."""

    def __init__(self, read_agent_memory: ReadAgentMemory) -> None:
        self._read = read_agent_memory

    def read(self, agent_id: UUID, query: str, *, top_k: int) -> tuple[MemoryHit, ...]:
        hits = self._read.read(agent_id, query, top_k=top_k)
        return tuple(
            MemoryHit(
                id=hit.entry.id,
                content=hit.entry.content,
                created_at=hit.entry.created_at,
                score=hit.score,
            )
            for hit in hits
        )
