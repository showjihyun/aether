"""spec 0004 2.4, 2.5, D-5, D-8, R-8, R-9 (P3-3): `KnowledgeSearch` outbound 포트.

`CompileContextUseCase` 가 지나는 검색 경계 — Knowledge Set **이름**(바인딩,
`AgentDefinition.knowledge`)으로 묻고 `SearchResult` 를 받습니다. 이름 → id 해석과
질의 임베딩은 어댑터(`adapters/outbound/knowledge_search/postgres.py`)가 맡습니다
— 이 유스케이스는 DB·임베딩 모델을 모릅니다(AR-9). 건네받지 않은 이름의 집합은
절대 보지 않습니다(R-9) — 조용히 다른 집합을 함께 검색하지 않습니다.
"""

from __future__ import annotations

from typing import Protocol

from aether_context.domain.knowledge import SearchResult


class KnowledgeSearch(Protocol):
    def search(
        self, set_names: tuple[str, ...], query: str, *, top_k: int
    ) -> tuple[SearchResult, ...]:
        """`set_names` 로 바인딩된 집합만 대상으로 `query` 를 검색해 상위 `top_k`.

        이름이 하나도 존재하지 않으면(바인딩되지 않음) 조용히 빈 튜플을 돌려줍니다
        — 다른 집합을 대신 보지 않습니다(R-9)."""
        ...
