"""spec 0004 2.1, 2.6, D-8, R-10 (P3-4): `MemoryReader` outbound 포트.

`CompileContextUseCase` 가 지나는 Memory 읽기 경계입니다. `aether_context` 는
`aether_memory` 를 import 하지 않습니다 — worker 의 `main` 이 `aether_memory` 의 읽기
유스케이스를 이 모양으로 감싸 꽂습니다(`KnowledgeSearch`·`Embedder` 와 같은 자리).
읽기는 Agent 단위입니다 — 건네받은 `agent_id` 의 기억만 돌려줍니다.
"""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from aether_context.domain.memory import MemoryHit


class MemoryReader(Protocol):
    def read(self, agent_id: UUID, query: str, *, top_k: int) -> tuple[MemoryHit, ...]:
        """`agent_id` 의 Memory 중 `query` 와 가까운 상위 `top_k`. 가까운 것이 먼저이고
        동점은 결정적으로 정렬되어 돌아옵니다(R-1)."""
        ...
