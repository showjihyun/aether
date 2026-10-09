"""spec 0004 2.4, D-4: `KnowledgeIngestionStatusMessage` — `aether:knowledge:
ingestions:status` 로 들어오는 투영 통지의 api 쪽 값 객체(`RunStatusMessage` 와
같은 모양, spec 0002 2.18)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel


class KnowledgeIngestionStatusMessage(BaseModel):
    ingestion_id: UUID
    status: Literal["running", "succeeded", "failed"]
    at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    failure_reason: str | None = None
