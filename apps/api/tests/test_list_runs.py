"""spec 0006 2.3, D-3: `ListRunsUseCase` - 저장소의 커서 페이지와 상태 필터를 그대로 전달합니다."""

from __future__ import annotations

from uuid import uuid4

from aether_api.application.usecases.list_runs import ListRunsUseCase
from aether_runtime.domain.run import RunStatus

from apps.api.tests.fakes import FakeRunDeclarationStore


def test_list_runs_pages_and_filters_by_status() -> None:
    """spec 0006 2.3: 상태 필터는 그 상태만, 커서는 다음 쪽을 잇는다."""
    store = FakeRunDeclarationStore()
    for _ in range(3):
        store.create(uuid4(), uuid4(), 1, "in", uuid4())
    running = store.create(uuid4(), uuid4(), 1, "in", uuid4())
    store.apply_status(
        running.run_id,
        seq=1,
        status=RunStatus.RUNNING,
        started_at=None,
        finished_at=None,
        failure_reason=None,
        trace_id=None,
    )
    list_runs = ListRunsUseCase(store)

    page1 = list_runs(3, None, None)
    page2 = list_runs(3, page1.next_cursor, None)
    only_running = list_runs(50, None, RunStatus.RUNNING)

    assert len(page1.items) == 3 and page1.next_cursor is not None
    assert len(page2.items) == 1 and page2.next_cursor is None
    assert [r.run_id for r in only_running.items] == [running.run_id]
