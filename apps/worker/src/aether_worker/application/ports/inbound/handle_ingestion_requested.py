"""spec 0004 2.4, D-4: `HandleIngestionRequested` — worker 의 적재 소비자
(`adapters/inbound/stream/ingestion_requested_consumer.py`)가 `aether:knowledge:
ingestions:requested` 에서 받은 메시지마다 부르는 inbound 포트.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID


@dataclass(frozen=True)
class IngestionRequestedMessage:
    """`aether:knowledge:ingestions:requested` 한 항목을 파싱한 값."""

    message_id: str
    ingestion_id: UUID
    knowledge_set_id: UUID
    source: str


@dataclass(frozen=True)
class HandleIngestionOutcome:
    """`ack=True` 면 소비자가 `XACK` 합니다."""

    ack: bool


class HandleIngestionRequested(Protocol):
    def __call__(self, message: IngestionRequestedMessage) -> HandleIngestionOutcome: ...
