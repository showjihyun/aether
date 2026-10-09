"""spec 0004 2.4, 2.9 (P3-2b): `Indexer` 포트의 고정 크기 + 겹침 구현.

문자 기준(토큰 기준이 아닌 이유는 `TokenCounter`·D-6 과 같습니다). 기본 1000/200
(`AETHER_KNOWLEDGE_CHUNK_CHARS`/`_OVERLAP`, spec 2.9) — 환경변수를 읽는 것은 worker
의 `main`(I/O)이고, 이 어댑터는 생성자 인자로만 받습니다(AR-9 의 취지 — 이 모듈
자신은 I/O 를 하지 않습니다).
"""

from __future__ import annotations

from aether_context.domain.knowledge import Chunk, Document

DEFAULT_CHUNK_CHARS = 1000
DEFAULT_OVERLAP_CHARS = 200


class FixedSizeIndexer:
    """`Indexer` 포트의 구현 — 문자 `chunk_chars` 크기, `overlap_chars` 겹침."""

    def __init__(
        self,
        chunk_chars: int = DEFAULT_CHUNK_CHARS,
        overlap_chars: int = DEFAULT_OVERLAP_CHARS,
    ) -> None:
        if chunk_chars <= 0:
            raise ValueError("chunk_chars must be positive")
        if overlap_chars < 0:
            raise ValueError("overlap_chars must not be negative")
        if overlap_chars >= chunk_chars:
            raise ValueError("overlap_chars must be smaller than chunk_chars")
        self._chunk_chars = chunk_chars
        self._overlap_chars = overlap_chars

    def chunk(self, document: Document) -> tuple[Chunk, ...]:
        content = document.content
        if not content:
            return ()

        step = self._chunk_chars - self._overlap_chars
        chunks: list[Chunk] = []
        start = 0
        index = 0
        length = len(content)
        while start < length:
            end = min(start + self._chunk_chars, length)
            chunks.append(
                Chunk(source_path=document.path, chunk_index=index, content=content[start:end])
            )
            if end == length:
                break
            index += 1
            start += step
        return tuple(chunks)
