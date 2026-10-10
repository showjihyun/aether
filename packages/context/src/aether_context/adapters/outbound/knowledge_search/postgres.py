"""spec 0004 2.4, 2.5, D-5, R-9 (P3-3): `KnowledgeSearch` 포트의 pgvector 구현.

`control.knowledge_sets` 에서 **건네받은 이름만** id 로 바꾸고(없는 이름은 결과에서
조용히 빠집니다 — 다른 집합을 보지 않습니다, R-9), `Embedder` 로 질의를 임베딩해
`KnowledgeStore.search` 를 부릅니다. `connect` 는 연결 팩토리입니다(`PostgresKnowledgeStore`
와 같은 패턴) — worker(`aether_data` 역할)가 이 어댑터를 씁니다. `aether_context` 는
`aether_runtime` 을 import 하지 않으므로(AR-3) 임베딩은 `Embedder` 포트를 지납니다.
"""

from __future__ import annotations

from collections.abc import Callable
from uuid import UUID

import psycopg

from aether_context.adapters.outbound.knowledge_store.postgres import PostgresKnowledgeStore
from aether_context.application.ports.outbound.embedder import Embedder
from aether_context.application.ports.outbound.knowledge_store import KnowledgeStore
from aether_context.domain.knowledge import SearchResult


class PostgresKnowledgeSearch:
    """`KnowledgeSearch` 포트 구현 — 이름 해석 + 질의 임베딩 + `KnowledgeStore.search`."""

    def __init__(
        self,
        connect: Callable[[], psycopg.Connection],
        embedder: Embedder,
        store: KnowledgeStore | None = None,
    ) -> None:
        self._connect = connect
        self._embedder = embedder
        self._store: KnowledgeStore = (
            store if store is not None else PostgresKnowledgeStore(connect)
        )

    def search(
        self, set_names: tuple[str, ...], query: str, *, top_k: int
    ) -> tuple[SearchResult, ...]:
        if not set_names:
            return ()

        set_ids = self._resolve_set_ids(set_names)
        if not set_ids:
            return ()

        query_embedding = self._embedder.embed([query])[0]
        return self._store.search(
            set_ids,
            query_embedding,
            embed_model_id=self._embedder.model_id,
            embed_dim=self._embedder.dim,
            top_k=top_k,
        )

    def _resolve_set_ids(self, set_names: tuple[str, ...]) -> tuple[UUID, ...]:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT id FROM control.knowledge_sets WHERE name = ANY(%s)",
                (list(set_names),),
            )
            rows = cur.fetchall()
        return tuple(row[0] for row in rows)
