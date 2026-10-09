"""spec 0004 2.4, D-4, D-9, R-5, R-6: `IngestKnowledgeUseCase` — `IngestKnowledge` 의
유일한 구현.

네 단계(`Connector -> Indexer -> Embedder -> KnowledgeStore`)를 고정된 순서로
지나갑니다. `Connector.list_documents` 가 이미 정렬된 순서를 주므로(결정성, 그
포트의 계약) 이 유스케이스는 그 순서를 그대로 보존합니다 — 집합·정렬 없는 `dict`
순회를 쓰지 않습니다(R-1 과 같은 습관).

**임베딩 호출(R-6).** 청크마다 `Embedder.embed` 를 한 번씩 부릅니다 — 배치로
묶지 않습니다. 그래서 fake 임베더의 호출 횟수가 항상 청크 수와 같습니다(판정
대상, `api-unit`).
"""

from __future__ import annotations

from aether_context.application.ports.inbound.ingest_knowledge import (
    IngestKnowledgeRequest,
    IngestKnowledgeResult,
)
from aether_context.application.ports.outbound.connector import Connector
from aether_context.application.ports.outbound.embedder import Embedder
from aether_context.application.ports.outbound.indexer import Indexer
from aether_context.application.ports.outbound.knowledge_store import KnowledgeStore
from aether_context.domain.knowledge import Chunk, EmbeddedChunk


class IngestKnowledgeUseCase:
    """`Connector`·`Indexer`·`Embedder`·`KnowledgeStore` 로 `IngestKnowledge` 를 구현."""

    def __init__(
        self,
        connector: Connector,
        indexer: Indexer,
        embedder: Embedder,
        store: KnowledgeStore,
    ) -> None:
        self._connector = connector
        self._indexer = indexer
        self._embedder = embedder
        self._store = store

    def __call__(self, request: IngestKnowledgeRequest) -> IngestKnowledgeResult:
        documents = self._connector.list_documents(request.source)

        chunks: list[Chunk] = []
        for document in documents:
            chunks.extend(self._indexer.chunk(document))

        embedded: list[EmbeddedChunk] = [self._embed(chunk) for chunk in chunks]

        self._store.replace_chunks(request.knowledge_set_id, request.ingestion_id, tuple(embedded))
        return IngestKnowledgeResult(chunk_count=len(embedded))

    def _embed(self, chunk: Chunk) -> EmbeddedChunk:
        vector = self._embedder.embed([chunk.content])[0]
        return EmbeddedChunk(
            source_path=chunk.source_path,
            chunk_index=chunk.chunk_index,
            content=chunk.content,
            embedding=tuple(vector),
            embed_model_id=self._embedder.model_id,
            embed_dim=self._embedder.dim,
        )
