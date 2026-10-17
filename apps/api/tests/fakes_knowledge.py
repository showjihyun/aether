"""spec 0004 2.4, D-4: `KnowledgeDeclarationStore`·`KnowledgeIngestionNotifier` 포트의
인메모리 fake — 컨테이너 없이 Knowledge 적재 **선언** 유스케이스를 돕니다
(architecture.md 3.1 "TDD" 이득, `apps/api/tests/fakes.py` 의 Run 쪽과 같은 패턴).
테스트 지원 코드이며 제품 코드가 아닙니다.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from aether_api.domain.knowledge import (
    IngestionStatus,
    KnowledgeIngestionPage,
    KnowledgeIngestionView,
    KnowledgeSetPage,
    KnowledgeSetView,
)

from apps.api.tests.fake_cursor import offset_of


def _default_clock() -> datetime:
    return datetime.now(UTC)


class FakeKnowledgeDeclarationStore:
    """`KnowledgeDeclarationStore` 포트 계약의 인메모리 구현."""

    def __init__(self, clock: type[datetime] | None = None) -> None:
        del clock
        self._sets: dict[UUID, KnowledgeSetView] = {}
        self._ingestions: dict[UUID, KnowledgeIngestionView] = {}
        self._ticks = 0

    def _tick(self) -> datetime:
        """만든 순서대로 1초씩 늘어나는 시각 - 정렬 방향 테스트가 결정적이도록."""
        self._ticks += 1
        return datetime(2026, 1, 1, tzinfo=UTC) + timedelta(seconds=self._ticks)

    def create_set(self, name: str) -> KnowledgeSetView:
        set_id = uuid4()
        view = KnowledgeSetView(id=set_id, name=name, created_at=self._tick())
        self._sets[set_id] = view
        return view

    def get_set(self, knowledge_set_id: UUID) -> KnowledgeSetView | None:
        return self._sets.get(knowledge_set_id)

    def list_sets(self, limit: int, cursor: str | None) -> KnowledgeSetPage:
        """정렬된 목록의 정수 오프셋을 감싼 불투명 커서."""
        ordered = sorted(self._sets.values(), key=lambda s: (s.created_at, str(s.id)))
        start = offset_of(cursor)
        page = ordered[start : start + limit]
        end = start + len(page)
        return KnowledgeSetPage(items=page, next_cursor=str(end) if end < len(ordered) else None)

    def list_ingestions(
        self,
        knowledge_set_id: UUID,
        limit: int,
        cursor: str | None,
        status: IngestionStatus | None = None,
    ) -> KnowledgeIngestionPage:
        """그 집합의 적재만, 정렬된 목록의 정수 오프셋을 감싼 불투명 커서."""
        ordered = sorted(
            (i for i in self._ingestions.values() if i.knowledge_set_id == knowledge_set_id),
            key=lambda i: (i.requested_at, str(i.id)),
            reverse=True,
        )
        if status is not None:
            ordered = [i for i in ordered if i.status == status]
        start = offset_of(cursor)
        page = ordered[start : start + limit]
        end = start + len(page)
        return KnowledgeIngestionPage(
            items=page, next_cursor=str(end) if end < len(ordered) else None
        )

    def create_ingestion(self, knowledge_set_id: UUID, source: str) -> KnowledgeIngestionView:
        ingestion_id = uuid4()
        view = KnowledgeIngestionView(
            id=ingestion_id,
            knowledge_set_id=knowledge_set_id,
            source=source,
            status="queued",
            requested_at=self._tick(),
            started_at=None,
            finished_at=None,
            failure_reason=None,
        )
        self._ingestions[ingestion_id] = view
        return view

    def get_ingestion(self, ingestion_id: UUID) -> KnowledgeIngestionView | None:
        return self._ingestions.get(ingestion_id)

    def apply_ingestion_status(
        self,
        ingestion_id: UUID,
        *,
        status: IngestionStatus,
        started_at: datetime | None,
        finished_at: datetime | None,
        failure_reason: str | None,
    ) -> bool:
        current = self._ingestions.get(ingestion_id)
        if current is None:
            return False
        self._ingestions[ingestion_id] = KnowledgeIngestionView(
            id=current.id,
            knowledge_set_id=current.knowledge_set_id,
            source=current.source,
            status=status,
            requested_at=current.requested_at,
            started_at=started_at if started_at is not None else current.started_at,
            finished_at=finished_at if finished_at is not None else current.finished_at,
            failure_reason=failure_reason if failure_reason is not None else current.failure_reason,
        )
        return True


class FakeKnowledgeIngestionNotifier:
    """`KnowledgeIngestionNotifier` 포트의 인메모리 구현. `should_fail` 이면
    `requested` 가 예외를 던집니다 — `RequestIngestionUseCase` 가 그 실패를 삼키고
    WARNING 을 남긴 뒤 정상 반환하는지 테스트가 증명합니다(spec 2.2 와 같은 취급)."""

    def __init__(self, *, should_fail: bool = False) -> None:
        self.calls: list[tuple[UUID, UUID, str]] = []
        self._should_fail = should_fail

    def requested(self, ingestion_id: UUID, knowledge_set_id: UUID, source: str) -> None:
        self.calls.append((ingestion_id, knowledge_set_id, source))
        if self._should_fail:
            raise RuntimeError("FakeKnowledgeIngestionNotifier: injected requested failure")
