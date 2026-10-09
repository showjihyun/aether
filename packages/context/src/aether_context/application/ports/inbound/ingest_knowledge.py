"""spec 0004 2.4, D-4, R-5, R-6: `IngestKnowledge` inbound 포트 — 적재 유스케이스의 계약.

worker 의 `HandleIngestionRequestedUseCase` 만 이 모듈(과 `domain.knowledge` 의 값
타입)을 봅니다(AR-12) — 구현(`application/usecases/ingest_knowledge.py`)과
`adapters` 는 보지 않습니다.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID


@dataclass(frozen=True)
class IngestKnowledgeRequest:
    """적재 선언 하나 — `knowledge_set_id`·`ingestion_id` 는 `control.knowledge_*`
    의 선언 행을 가리키고(D-4), `source` 는 `Connector` 가 읽을 위치(디렉터리 경로)."""

    knowledge_set_id: UUID
    ingestion_id: UUID
    source: str


@dataclass(frozen=True)
class IngestKnowledgeResult:
    """적재가 저장한 청크 수 — 호출자(worker)가 상태를 결정하는 데 씁니다."""

    chunk_count: int


class IngestKnowledge(Protocol):
    def __call__(self, request: IngestKnowledgeRequest) -> IngestKnowledgeResult:
        """`request.source` 를 읽어 청크로 쪼개고 임베딩해 `KnowledgeStore` 에
        저장합니다(R-5, R-6)."""
        ...
