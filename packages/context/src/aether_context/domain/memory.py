"""spec 0004 2.6, D-8, R-10 (P3-4): Memory 읽기 결과와 그 렌더링.

`aether_memory` 의 타입을 import 하지 않습니다 — 이 패키지가 `MemoryReader` 포트
(`application/ports/outbound/memory_reader.py`)에 요구하는 모양을 자기 값 타입으로
선언하고, worker 의 `main` 이 `aether_memory` 의 읽기 유스케이스를 이 모양으로 꽂습니다
(`KnowledgeSearch` 와 같은 자리). 표준 `dataclass` 만 씁니다(AR-9).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class MemoryHit:
    """`MemoryReader.read` 한 건. `score` 는 코사인 거리 — 작을수록 가깝습니다."""

    id: UUID
    content: str
    created_at: datetime
    score: float


def render_memory_block(hit: MemoryHit) -> str:
    """spec R-10, D-8: Memory 하나를 전용 블록으로 렌더링합니다. `render_knowledge_block`
    과 **다른 표지**입니다 — Knowledge 는 `trust=untrusted` + 출처(조직이 소유한 사실)이고
    Memory 는 `verified=false` + 기록 시각(에이전트가 남긴, 검증 전 경험)입니다. 둘이 같은
    문자열이 되면 경험이 사실로 읽힐 수 있습니다(domain 3절)."""
    return (
        f"[memory id={hit.id} created={hit.created_at.isoformat()} verified=false]"
        f"{hit.content}"
        "[/memory]"
    )
