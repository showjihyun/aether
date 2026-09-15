"""spec 0002 2.7, 2.18, D-4: `RunEventReader` 아웃바운드 포트.

`ReadRunEventsUseCase` 가 스트림 존재 확인과 이벤트 읽기에 쓰는 계약입니다. Redis
구현(`adapters/outbound/redis/run_event_reader.py`)은 `redis.asyncio` 의 블록
`XREAD` 를 씁니다 — 이 포트 자체는 `redis` 를 import 하지 않습니다(AR-9, domain·
application 은 프레임워크·I/O 를 모릅니다).
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Protocol
from uuid import UUID

from aether_runtime.domain.events import RunEvent


class RunEventReader(Protocol):
    """`aether:runs:{run_id}:events` 스트림의 읽기 계약(spec 2.7)."""

    async def stream_exists(self, run_id: UUID) -> bool:
        """스트림 키가 있으면 `True`. 없으면 `False`(TTL 만료, 또는 아직 발행 전)."""
        ...

    def read(self, run_id: UUID, after_seq: int | None, block_ms: int) -> AsyncIterator[RunEvent]:
        """`after_seq` 보다 큰 `seq` 부터 이벤트를 순서대로 냅니다.

        읽을 게 없으면 최대 `block_ms` 밀리초 블록하고(`XREAD BLOCK`), 그래도 없으면
        빈 채로 돌아와 다시 블록합니다 — 한 번에 무한정 블록하지 않아 호출부(usecase
        → HTTP 어댑터)가 매 `block_ms` 마다 취소 지점(`asyncio.CancelledError`)을
        얻습니다(R-3, C-4: 클라이언트 단절이 이 읽기를 취소해야 합니다).
        """
        ...
