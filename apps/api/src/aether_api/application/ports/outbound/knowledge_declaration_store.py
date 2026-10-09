"""spec 0004 2.4, 2.8, D-4: `control.knowledge_sets`/`control.knowledge_ingestions`
에 대한 outbound 포트.

`control.runs` 의 `RunDeclarationStore` 와 같은 모양(spec 0002 2.1) — Control Plane
은 선언·투영만 다룹니다. 실행 부산물(`data.knowledge_chunks`)은 이 포트가 모릅니다.
"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol
from uuid import UUID

from aether_api.domain.knowledge import IngestionStatus, KnowledgeIngestionView, KnowledgeSetView


class KnowledgeDeclarationStore(Protocol):
    def create_set(self, name: str) -> KnowledgeSetView:
        """새 `control.knowledge_sets` 행을 만듭니다. 커밋까지 이 호출 안에서 끝납니다."""
        ...

    def get_set(self, knowledge_set_id: UUID) -> KnowledgeSetView | None:
        """없으면 `None` — 유스케이스가 `KnowledgeSetNotFound` 로 바꿉니다."""
        ...

    def create_ingestion(self, knowledge_set_id: UUID, source: str) -> KnowledgeIngestionView:
        """`status = queued` 로 새 `control.knowledge_ingestions` 행을 만듭니다."""
        ...

    def get_ingestion(self, ingestion_id: UUID) -> KnowledgeIngestionView | None:
        """없으면 `None` — 유스케이스가 `KnowledgeIngestionNotFound` 로 바꿉니다."""
        ...

    def apply_ingestion_status(
        self,
        ingestion_id: UUID,
        *,
        status: IngestionStatus,
        started_at: datetime | None,
        finished_at: datetime | None,
        failure_reason: str | None,
    ) -> bool:
        """상태를 적용합니다. 없는 `ingestion_id` 면 `False`(멱등 무시, D-2 와 같은
        취급) — `started_at`/`finished_at`/`failure_reason` 이 `None` 이면 기존
        값을 그대로 둡니다(`COALESCE`)."""
        ...
