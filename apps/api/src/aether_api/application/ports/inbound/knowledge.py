"""spec 0004 2.4, D-4: Knowledge 적재 선언 경로의 inbound 포트 — `agents.py`/`runs.py`
와 같은 관례(요청·응답 모델은 `adapters/inbound/http/knowledge.py`)."""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from aether_api.domain.knowledge import KnowledgeIngestionView, KnowledgeSetView


class CreateKnowledgeSet(Protocol):
    def __call__(self, name: str) -> KnowledgeSetView: ...


class RequestIngestion(Protocol):
    def __call__(self, knowledge_set_id: UUID, source: str) -> KnowledgeIngestionView: ...


class GetIngestion(Protocol):
    def __call__(self, ingestion_id: UUID) -> KnowledgeIngestionView: ...
