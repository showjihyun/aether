"""spec 0004 2.4, D-4: `KnowledgeIngestionNotifier` — 적재 실행 통지의 outbound 포트.

`aether:knowledge:ingestions:requested` 에 **쓰기만** 하는 쪽입니다(`RunNotifier` 와
같은 모양, spec 0002 2.18). `knowledge_set_id`·`source` 를 함께 실어 보내 worker 가
`control.knowledge_sets`/`knowledge_ingestions` 를 다시 읽지 않게 합니다(`RunNotifier`
가 `agent_version_id` 를 함께 보내는 것과 같은 이유).
"""

from __future__ import annotations

from typing import Protocol
from uuid import UUID


class KnowledgeIngestionNotifier(Protocol):
    def requested(self, ingestion_id: UUID, knowledge_set_id: UUID, source: str) -> None: ...
