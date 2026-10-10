"""spec 0004 2.1, 2.6, AR-3 (P3-4): `MemoryReaderAdapter` — `aether_memory` 의 읽기
유스케이스를 `aether_context` 의 `MemoryReader` 포트 모양으로 바꿉니다. 두 패키지는 서로를
import 하지 않으므로(조립은 worker 의 몫) 이 변환이 worker 에 있습니다.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from aether_context.domain.memory import MemoryHit as ContextMemoryHit
from aether_memory.domain.memory import MemoryEntry, MemoryHit
from aether_worker.adapters.outbound.memory.reader import MemoryReaderAdapter

_AGENT = uuid.UUID(int=1)
_CREATED = datetime(2026, 10, 1, tzinfo=UTC)


class _FakeRead:
    def __init__(self, hits: tuple[MemoryHit, ...]) -> None:
        self.hits = hits
        self.calls: list[tuple[uuid.UUID, str, int]] = []

    def read(self, agent_id: uuid.UUID, query: str, *, top_k: int) -> tuple[MemoryHit, ...]:
        self.calls.append((agent_id, query, top_k))
        return self.hits


def test_adapter_maps_hits_preserving_order_and_forwards_arguments() -> None:
    hits = tuple(
        MemoryHit(
            entry=MemoryEntry(
                id=uuid.UUID(int=n),
                agent_id=_AGENT,
                run_id=None,
                content=f"c{n}",
                created_at=_CREATED,
            ),
            score=0.1 * n,
        )
        for n in (3, 1, 2)
    )
    read = _FakeRead(hits)

    result = MemoryReaderAdapter(read).read(_AGENT, "q", top_k=4)

    assert read.calls == [(_AGENT, "q", 4)]
    assert result == tuple(
        ContextMemoryHit(id=uuid.UUID(int=n), content=f"c{n}", created_at=_CREATED, score=0.1 * n)
        for n in (3, 1, 2)
    )
