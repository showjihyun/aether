"""spec 0004 2.4, D-4, D-9, R-6: `IngestKnowledgeUseCase` 의 계약 테스트.

컨테이너·네트워크 없음 — `Connector`·`Indexer`·`Embedder`·`KnowledgeStore` 포트
전부를 fake 로 꽂습니다(아키텍처 "포트 계약 테스트" 이득). 구현 뒤에 작성됐습니다
(red→green 순서 위반, 보고에 기록).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import uuid4

from aether_context.application.ports.inbound.ingest_knowledge import IngestKnowledgeRequest
from aether_context.application.usecases.ingest_knowledge import IngestKnowledgeUseCase
from aether_context.domain.knowledge import Chunk, Document, EmbeddedChunk, SearchResult


class _FakeConnector:
    def __init__(self, documents: tuple[Document, ...]) -> None:
        self._documents = documents

    def list_documents(self, source: str) -> tuple[Document, ...]:
        del source
        return self._documents


class _FakeIndexer:
    """문서를 `chunks_per_doc` 개로 고정 분할 — 경계 로직은 `FixedSizeIndexer` 가
    따로 검증하므로 여기서는 호출 횟수·순서만 봅니다."""

    def __init__(self, chunks_per_doc: int = 2) -> None:
        self._chunks_per_doc = chunks_per_doc

    def chunk(self, document: Document) -> tuple[Chunk, ...]:
        return tuple(
            Chunk(source_path=document.path, chunk_index=i, content=f"{document.content}#{i}")
            for i in range(self._chunks_per_doc)
        )


@dataclass
class _FakeEmbedder:
    """spec R-6: `embed` 호출 수를 기록 — 청크마다 한 번씩 불려야 합니다."""

    model_id: str = "fake-embed"
    dim: int = 3
    calls: list[list[str]] = field(default_factory=list)

    def embed(self, texts: list[str]) -> list[list[float]]:
        self.calls.append(texts)
        return [[float(len(t)), 0.0, 1.0] for t in texts]


@dataclass
class _FakeKnowledgeStore:
    replaced: list[tuple[object, object, tuple[EmbeddedChunk, ...]]] = field(default_factory=list)

    def replace_chunks(self, knowledge_set_id, ingestion_id, chunks) -> None:  # type: ignore[no-untyped-def]
        self.replaced.append((knowledge_set_id, ingestion_id, chunks))

    def search(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        return ()


def test_embed_call_count_equals_chunk_count() -> None:
    """spec R-6: fake gateway(embedder) 의 `embed` 호출 수 = 청크 수."""
    documents = (
        Document(path="a.txt", content="A"),
        Document(path="b.txt", content="B"),
        Document(path="c.txt", content="C"),
    )
    connector = _FakeConnector(documents)
    indexer = _FakeIndexer(chunks_per_doc=2)
    embedder = _FakeEmbedder()
    store = _FakeKnowledgeStore()
    usecase = IngestKnowledgeUseCase(connector, indexer, embedder, store)

    knowledge_set_id, ingestion_id = uuid4(), uuid4()
    result = usecase(
        IngestKnowledgeRequest(
            knowledge_set_id=knowledge_set_id, ingestion_id=ingestion_id, source="/irrelevant"
        )
    )

    expected_chunk_count = len(documents) * 2
    assert result.chunk_count == expected_chunk_count
    assert len(embedder.calls) == expected_chunk_count


def test_embedded_chunks_carry_model_id_and_dim() -> None:
    """spec D-9: 청크에 임베딩 모델 id·차원이 함께 저장됩니다."""
    documents = (Document(path="a.txt", content="A"),)
    store = _FakeKnowledgeStore()
    usecase = IngestKnowledgeUseCase(
        _FakeConnector(documents), _FakeIndexer(chunks_per_doc=1), _FakeEmbedder(), store
    )
    usecase(IngestKnowledgeRequest(knowledge_set_id=uuid4(), ingestion_id=uuid4(), source="/x"))

    _, _, chunks = store.replaced[0]
    assert len(chunks) == 1
    chunk = chunks[0]
    assert isinstance(chunk, EmbeddedChunk)
    assert chunk.embed_model_id == "fake-embed"
    assert chunk.embed_dim == 3
    assert chunk.embedding == (3.0, 0.0, 1.0)  # len("A#0") == 3


def test_preserves_document_and_chunk_order() -> None:
    """R-1 과 같은 습관: 정렬된 입력 순서를 그대로 보존합니다(집합·비결정 순회 없음)."""
    documents = tuple(Document(path=f"{i}.txt", content=str(i)) for i in range(5))
    store = _FakeKnowledgeStore()
    usecase = IngestKnowledgeUseCase(
        _FakeConnector(documents), _FakeIndexer(chunks_per_doc=1), _FakeEmbedder(), store
    )
    usecase(IngestKnowledgeRequest(knowledge_set_id=uuid4(), ingestion_id=uuid4(), source="/x"))

    _, _, chunks = store.replaced[0]
    assert [c.source_path for c in chunks] == [f"{i}.txt" for i in range(5)]


def test_search_result_type_available_for_future_units() -> None:
    """P3-3 가 바로 쓸 수 있는 값 타입이 이미 있는지 — import 만 확인합니다."""
    result = SearchResult(source_path="a.txt", chunk_index=0, content="x", score=0.1)
    assert result.score == 0.1
