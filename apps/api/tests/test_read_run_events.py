"""spec 0002 2.7, D-4, R-3: `ReadRunEventsUseCase` — fake `RunEventReader` +
`FakeRunDeclarationStore` 로, 컨테이너 없이(AR-9).

- 순서 그대로 전달, `run.finished` 뒤 종료
- `after_seq`(= `Last-Event-ID`)로 재개
- 스트림 없음 + run 종결 → 합성 `run.finished` 1건
- 스트림 없음 + run 미종결 → 첫 이벤트가 심어질 때까지 기다렸다가 전달
- 없는 run → `RunNotFound`

비동기 테스트는 `anyio` 플러그인(`@pytest.mark.anyio`, 루트 `conftest.py` 의
`anyio_backend` fixture 가 `asyncio` 로 고정)을 씁니다. 대기는 `asyncio.Event` 뿐이고
`sleep` 은 쓰지 않습니다(R-11).
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from aether_api.application.usecases.read_run_events import ReadRunEventsUseCase
from aether_api.domain.run import RunNotFound
from aether_runtime.domain.events import EventType, RunEvent
from aether_runtime.domain.run import RunStatus

from apps.api.tests.fakes import FakeRunDeclarationStore, FakeRunEventReader

pytestmark = pytest.mark.anyio


def _event(run_id: UUID, seq: int, event_type: EventType, payload: dict[str, object]) -> RunEvent:
    return RunEvent(
        run_id=run_id,
        seq=seq,
        at=datetime.now(UTC),
        type=event_type,
        payload=payload,
    )


async def _collect(ait: AsyncIterator[RunEvent], limit: int = 100) -> list[RunEvent]:
    events: list[RunEvent] = []
    async for event in ait:
        events.append(event)
        if len(events) >= limit:
            break
    return events


async def test_events_are_delivered_in_seeded_order_and_stop_after_run_finished() -> None:
    runs = FakeRunDeclarationStore()
    created = runs.create(uuid4(), uuid4(), 1, "hi", uuid4())
    run_id = created.run_id
    reader = FakeRunEventReader()
    reader.seed(
        run_id,
        [
            _event(run_id, 1, "run.status", {"status": "running"}),
            _event(run_id, 2, "task.started", {"task_id": "t1", "step": 1}),
            _event(run_id, 3, "run.finished", {"status": "succeeded"}),
        ],
    )
    use_case = ReadRunEventsUseCase(reader, runs)

    events = await _collect(use_case(run_id, None))

    assert [e.seq for e in events] == [1, 2, 3]
    assert [e.type for e in events] == ["run.status", "task.started", "run.finished"]


async def test_after_seq_resumes_from_last_event_id() -> None:
    runs = FakeRunDeclarationStore()
    created = runs.create(uuid4(), uuid4(), 1, "hi", uuid4())
    run_id = created.run_id
    reader = FakeRunEventReader()
    reader.seed(
        run_id,
        [
            _event(run_id, 1, "run.status", {"status": "running"}),
            _event(run_id, 2, "task.started", {"task_id": "t1", "step": 1}),
            _event(run_id, 3, "run.finished", {"status": "succeeded"}),
        ],
    )
    use_case = ReadRunEventsUseCase(reader, runs)

    events = await _collect(use_case(run_id, 1))

    assert [e.seq for e in events] == [2, 3]


async def test_missing_stream_and_terminal_run_yields_one_synthetic_run_finished() -> None:
    runs = FakeRunDeclarationStore()
    created = runs.create(uuid4(), uuid4(), 1, "hi", uuid4())
    run_id = created.run_id
    runs.apply_status(
        run_id,
        seq=5,
        status=RunStatus.SUCCEEDED,
        started_at=None,
        finished_at=datetime.now(UTC),
        failure_reason=None,
        trace_id=None,
    )
    reader = FakeRunEventReader()  # 스트림을 심지 않음 — stream_exists() == False
    use_case = ReadRunEventsUseCase(reader, runs)

    events = await _collect(use_case(run_id, None))

    assert len(events) == 1
    assert events[0].type == "run.finished"
    assert events[0].payload == {"status": "succeeded"}


async def test_missing_stream_and_non_terminal_run_waits_for_the_first_event() -> None:
    """R-3: 스트림이 아직 없고 run 이 종결이 아니면 스트림이 생길 때까지 기다립니다
    (`XREAD BLOCK` 은 없는 키에도 동작 — fake 는 `asyncio.Event` 로 재현)."""
    runs = FakeRunDeclarationStore()
    created = runs.create(uuid4(), uuid4(), 1, "hi", uuid4())
    run_id = created.run_id
    reader = FakeRunEventReader()
    use_case = ReadRunEventsUseCase(reader, runs)

    gen = use_case(run_id, None)
    task = asyncio.ensure_future(gen.__anext__())
    # `asyncio.wait_for(..., timeout=0)` 은 이벤트 루프에 정확히 한 번 실행 기회를 주고
    # 그래도 끝나지 않으면 `TimeoutError` — `sleep(0)` 없이 "아직 대기 중" 을 확인합니다
    # (R-11: 이 테스트 트리에서 `time.sleep`/`asyncio.sleep` 은 금지).
    with pytest.raises(TimeoutError):
        await asyncio.wait_for(asyncio.shield(task), timeout=0)
    assert not task.done(), "스트림이 없을 때는 이벤트가 생길 때까지 기다려야 합니다"

    reader.push(run_id, _event(run_id, 1, "run.status", {"status": "running"}))
    first = await asyncio.wait_for(task, timeout=5.0)

    assert first.seq == 1
    assert first.type == "run.status"


async def test_missing_run_raises_run_not_found() -> None:
    runs = FakeRunDeclarationStore()
    reader = FakeRunEventReader()
    use_case = ReadRunEventsUseCase(reader, runs)

    with pytest.raises(RunNotFound):
        await _collect(use_case(uuid4(), None))
