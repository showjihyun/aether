"""spec 0004 2.4, D-4: `IngestKnowledge`(아ether_context inbound 포트)의 공용 fake.

`tests/arch/test_fake_duplication.py`(improvement-log 2026-09-28-001)가 같은 포트의
fake 가 여러 곳에 흩어지는 것을 막습니다 — `apps/worker/tests/test_handle_
ingestion_requested.py` 와 `apps/worker/tests/test_knowledge_ingestion_status_end_
to_end.py` 가 이 하나를 같이 씁니다. 테스트 지원 코드이며 제품 코드가 아닙니다.
"""

from __future__ import annotations

from aether_context.application.ports.inbound.ingest_knowledge import (
    IngestKnowledgeRequest,
    IngestKnowledgeResult,
)


class FakeIngestKnowledge:
    """`IngestKnowledge` 의 인메모리 구현. `error` 가 있으면 호출마다 그 예외를
    던집니다 — 없으면 `chunk_count`(기본 3)로 성공합니다. `calls` 에 받은 요청을
    순서대로 기록합니다."""

    def __init__(self, *, error: Exception | None = None, chunk_count: int = 3) -> None:
        self._error = error
        self._chunk_count = chunk_count
        self.calls: list[IngestKnowledgeRequest] = []

    def __call__(self, request: IngestKnowledgeRequest) -> IngestKnowledgeResult:
        self.calls.append(request)
        if self._error is not None:
            raise self._error
        return IngestKnowledgeResult(chunk_count=self._chunk_count)
