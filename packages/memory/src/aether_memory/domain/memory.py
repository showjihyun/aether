"""spec 0004 2.6, 2.8, D-9, D-10 (P3-4): Memory 의 값 타입.

Memory 는 이전 Run 에서 유래한, 에이전트가 남긴 경험입니다(domain.md 3절) — 검증 전에는
신뢰하지 않습니다. Knowledge 와 타입도 저장소도 따로 둡니다(R-10). 표준 `dataclass`·
`uuid`·`datetime` 만 씁니다(AR-9).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class MemoryEntry:
    """`data.agent_memory` 의 행 하나(임베딩 제외). `run_id` 는 어느 Run 이 남겼는가 —
    출처를 추적하기 위한 것이고, Run 없이 쓰인 기억에는 `None` 입니다."""

    id: UUID
    agent_id: UUID
    run_id: UUID | None
    content: str
    created_at: datetime


@dataclass(frozen=True)
class MemoryHit:
    """검색 결과 한 건. `score` 는 코사인 거리 — 작을수록 가깝습니다."""

    entry: MemoryEntry
    score: float


@dataclass(frozen=True)
class NewMemory:
    """저장할 기억 하나 — 임베딩과 함께 **모델 id·차원**을 싣습니다(D-9). `id`·
    `created_at` 은 저장소가 정합니다."""

    agent_id: UUID
    run_id: UUID | None
    content: str
    embedding: tuple[float, ...]
    embed_model_id: str
    embed_dim: int
