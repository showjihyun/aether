"""spec 0004 2.4, D-4: `KnowledgeIngestionStatusNotifier` outbound 포트 —
`aether:knowledge:ingestions:status` 로 가는 투영 통지(`StatusNotifier` 와 같은
모양, spec 0002 2.18). api 의 `IngestionStatusConsumer` 가 이 스트림을 읽어
`control.knowledge_ingestions` 에 적용합니다(control role, worker 는 쓰지 않음).
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Protocol
from uuid import UUID

IngestionStatus = Literal["running", "succeeded", "failed"]


class KnowledgeIngestionStatusNotifier(Protocol):
    def notify(
        self,
        ingestion_id: UUID,
        status: IngestionStatus,
        at: datetime,
        *,
        started_at: datetime | None = None,
        finished_at: datetime | None = None,
        failure_reason: str | None = None,
    ) -> None: ...
