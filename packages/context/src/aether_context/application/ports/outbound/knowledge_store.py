"""spec 0004 2.4, 2.8, D-2, D-9, C-3, R-5: `KnowledgeStore` outbound 포트.

실제 구현은 pgvector 어댑터(`adapters/outbound/knowledge_store/postgres.py`,
`data.knowledge_chunks`). 이 단위(P3-2b)는 `search` 까지만 만듭니다 — 검색 결과를
Context 에 넣는 것은 P3-3 입니다.
"""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from aether_context.domain.knowledge import EmbeddedChunk, SearchResult

DEFAULT_TOP_K = 5
"""spec D-2: 상위 k 기본값 — `AgentDefinition` 이 바꿀 수 있습니다(P3-3 범위)."""


class EmbeddingMismatch(Exception):
    """spec C-3, D-9: 검색 시점의 임베딩 모델·차원이 저장된 청크와 다릅니다 —
    자동 재적재는 하지 않고, 이 오류로 **재적재를 요구**합니다(조용히 섞지 않음)."""

    def __init__(
        self,
        *,
        requested_model_id: str,
        requested_dim: int,
        stored_model_id: str,
        stored_dim: int,
    ) -> None:
        super().__init__(
            "embedding model/dim mismatch: requested "
            f"({requested_model_id}, dim={requested_dim}) but stored chunks use "
            f"({stored_model_id}, dim={stored_dim}) — re-ingest required"
        )
        self.requested_model_id = requested_model_id
        self.requested_dim = requested_dim
        self.stored_model_id = stored_model_id
        self.stored_dim = stored_dim


class KnowledgeStore(Protocol):
    def replace_chunks(
        self,
        knowledge_set_id: UUID,
        ingestion_id: UUID,
        chunks: tuple[EmbeddedChunk, ...],
    ) -> None:
        """`knowledge_set_id` 의 기존 청크를 전부 지우고 `chunks` 로 교체합니다
        (재적재 시 교체 — append-only 가 아닙니다, spec 2.8)."""
        ...

    def search(
        self,
        knowledge_set_ids: tuple[UUID, ...],
        query_embedding: list[float],
        *,
        embed_model_id: str,
        embed_dim: int,
        top_k: int = DEFAULT_TOP_K,
    ) -> tuple[SearchResult, ...]:
        """`knowledge_set_ids` 안에서 코사인 거리 오름차순 상위 `top_k`(spec D-2).

        저장된 청크의 임베딩 모델·차원이 `embed_model_id`/`embed_dim` 과 다르면
        `EmbeddingMismatch` 를 던집니다(C-3) — 자동으로 섞어 계산하지 않습니다.
        """
        ...
