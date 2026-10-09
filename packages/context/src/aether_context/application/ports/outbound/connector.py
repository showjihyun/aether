"""spec 0004 2.4 (P3-2b): `Connector` outbound 포트 — 적재 소스에서 문서를 읽습니다.

실제 구현은 `adapters/outbound/connector/filesystem.py`(Filesystem 하나, spec
0003 D-6 과 같은 범위 선택) 입니다. `list_documents` 는 **정렬된 순서**로 돌려줘야
합니다 — 디렉터리 순회가 결정적이지 않으면 청크 순서·`api-unit` 의 결정성 판정이
깨집니다(P3-1 에서 배운 것과 같은 함정).
"""

from __future__ import annotations

from typing import Protocol

from aether_context.domain.knowledge import Document


class Connector(Protocol):
    def list_documents(self, source: str) -> tuple[Document, ...]:
        """`source` 아래의 문서 전부를 경로 **오름차순 정렬**로 돌려줍니다."""
        ...
