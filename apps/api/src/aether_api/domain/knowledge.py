"""spec 0004 2.4, 2.8, D-4: Control Plane 의 Knowledge 적재 **선언** 투영 값 객체.

`control.knowledge_sets`/`control.knowledge_ingestions` 의 선언·투영 열만 담습니다
— 실행(청크·임베딩, `data.knowledge_chunks`)은 worker(`aether_context`)의 몫이고
api 는 모릅니다(AR-7 과 같은 경계).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal
from uuid import UUID

IngestionStatus = Literal["queued", "running", "succeeded", "failed"]


@dataclass(frozen=True)
class KnowledgeSetView:
    id: UUID
    name: str
    created_at: datetime


class KnowledgeSetNotFound(Exception):
    """주어진 `knowledge_set_id` 가 없습니다(404 `knowledge_set_not_found`)."""


@dataclass(frozen=True)
class KnowledgeIngestionView:
    """`control.knowledge_ingestions` 한 행의 선언·투영 열(spec 2.8)."""

    id: UUID
    knowledge_set_id: UUID
    source: str
    status: IngestionStatus
    requested_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    failure_reason: str | None


class KnowledgeIngestionNotFound(Exception):
    """주어진 `ingestion_id` 가 없습니다(404 `knowledge_ingestion_not_found`)."""
