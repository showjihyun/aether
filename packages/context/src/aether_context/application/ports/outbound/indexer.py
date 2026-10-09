"""spec 0004 2.4 (P3-2b): `Indexer` outbound 포트 — 문서 하나를 청크로 쪼갭니다.

실제 구현은 `adapters/outbound/indexer/fixed_size.py` — 문자 기준 고정 크기 +
겹침(기본 1000/200, `AETHER_KNOWLEDGE_CHUNK_CHARS`/`_OVERLAP`). 토큰 기준이 아닌
이유는 `TokenCounter` 와 같습니다(D-6 — 토크나이저 의존을 들이지 않습니다).
"""

from __future__ import annotations

from typing import Protocol

from aether_context.domain.knowledge import Chunk, Document


class Indexer(Protocol):
    def chunk(self, document: Document) -> tuple[Chunk, ...]:
        """`document` 를 `chunk_index` 오름차순의 청크로 쪼갭니다. 결정적입니다 —
        같은 문서는 항상 같은 청크 목록을 냅니다."""
        ...
