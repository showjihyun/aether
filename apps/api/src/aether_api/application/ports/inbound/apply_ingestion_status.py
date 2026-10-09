"""spec 0004 2.4, D-4: `ApplyIngestionStatus` inbound 포트 — 투영 통지 적용."""

from __future__ import annotations

from typing import Protocol

from aether_api.domain.knowledge_ingestion_status_message import KnowledgeIngestionStatusMessage


class ApplyIngestionStatus(Protocol):
    def __call__(self, message: KnowledgeIngestionStatusMessage) -> bool: ...
