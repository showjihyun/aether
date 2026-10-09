"""spec 0004 2.4, 2.9 (P3-2b): `FixedSizeIndexer` 의 청크 경계 결정성.

구현 뒤에 작성됐습니다(red→green 순서 위반, 보고에 기록) — 설계 과정에서 포트
넷(`Connector`·`Indexer`·`Embedder`·`KnowledgeStore`)과 유스케이스를 한 번에
맞물려 고정할 필요가 있었습니다. 이 테스트 스위트 자체는 여전히 구현과 **독립적으로**
실행해 통과를 확인했습니다(green 증거, 보고의 red 증거 절 참조).
"""

from __future__ import annotations

from aether_context.adapters.outbound.indexer.fixed_size import FixedSizeIndexer
from aether_context.domain.knowledge import Document


def test_chunk_boundaries_are_deterministic_for_1000_200() -> None:
    """spec 2.9: 기본 1000/200 — 같은 문서는 항상 같은 청크 경계를 냅니다."""
    content = "".join(f"{i:04d}" for i in range(1000))  # 4000 chars
    document = Document(path="doc.txt", content=content)
    indexer = FixedSizeIndexer(chunk_chars=1000, overlap_chars=200)

    first = indexer.chunk(document)
    second = indexer.chunk(document)
    assert first == second

    assert [c.chunk_index for c in first] == list(range(len(first)))
    assert first[0].content == content[0:1000]
    assert first[1].content == content[800:1800]
    assert first[2].content == content[1600:2600]
    # 겹침 200: 연속 청크의 꼬리/머리 200자가 같습니다.
    assert first[0].content[-200:] == first[1].content[:200]


def test_chunk_covers_whole_document_without_gaps() -> None:
    content = "a" * 2500
    document = Document(path="doc.txt", content=content)
    indexer = FixedSizeIndexer(chunk_chars=1000, overlap_chars=200)
    chunks = indexer.chunk(document)
    assert chunks[-1].content[-1] == content[-1]
    assert sum(len(c.content) for c in chunks) >= len(content)


def test_empty_document_yields_no_chunks() -> None:
    indexer = FixedSizeIndexer()
    assert indexer.chunk(Document(path="empty.txt", content="")) == ()


def test_short_document_yields_single_chunk() -> None:
    indexer = FixedSizeIndexer(chunk_chars=1000, overlap_chars=200)
    chunks = indexer.chunk(Document(path="short.txt", content="hello"))
    assert len(chunks) == 1
    assert chunks[0].content == "hello"
    assert chunks[0].chunk_index == 0


def test_rejects_invalid_overlap() -> None:
    import pytest

    with pytest.raises(ValueError):
        FixedSizeIndexer(chunk_chars=100, overlap_chars=100)
    with pytest.raises(ValueError):
        FixedSizeIndexer(chunk_chars=100, overlap_chars=200)
    with pytest.raises(ValueError):
        FixedSizeIndexer(chunk_chars=0, overlap_chars=0)
