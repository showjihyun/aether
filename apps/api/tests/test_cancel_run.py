"""spec 0002 2.2, D-11: `CancelRunUseCase` — 멱등, 종결이어도 현재 상태로 202 용 뷰."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from aether_api.application.usecases.cancel_run import CancelRunUseCase
from aether_api.domain.run import RunNotFound
from aether_runtime.domain.run import RunStatus

from apps.api.tests.fakes import FakeRunDeclarationStore


def test_cancel_run_sets_cancel_requested_at() -> None:
    store = FakeRunDeclarationStore()
    created = store.create(uuid4(), uuid4(), 1, "do it", uuid4())
    clock_values = iter([datetime(2026, 1, 1, tzinfo=UTC)])
    cancel_run = CancelRunUseCase(store, clock=lambda: next(clock_values))

    view = cancel_run(created.run_id)

    assert view.cancel_requested_at == datetime(2026, 1, 1, tzinfo=UTC)


def test_cancel_run_is_idempotent_and_keeps_the_first_timestamp() -> None:
    store = FakeRunDeclarationStore()
    created = store.create(uuid4(), uuid4(), 1, "do it", uuid4())
    first_at = datetime(2026, 1, 1, tzinfo=UTC)
    second_at = datetime(2026, 1, 2, tzinfo=UTC)
    clock_values = iter([first_at, second_at])
    cancel_run = CancelRunUseCase(store, clock=lambda: next(clock_values))

    first_view = cancel_run(created.run_id)
    second_view = cancel_run(created.run_id)

    assert first_view.cancel_requested_at == first_at
    assert second_view.cancel_requested_at == first_at


def test_cancel_run_on_terminal_run_still_returns_current_status() -> None:
    """spec 2.2: Run 이 이미 종결이면 현재 상태로 202 (예외를 던지지 않습니다)."""
    store = FakeRunDeclarationStore()
    created = store.create(uuid4(), uuid4(), 1, "do it", uuid4())
    store.apply_status(
        created.run_id,
        seq=1,
        status=RunStatus.SUCCEEDED,
        started_at=None,
        finished_at=datetime(2026, 1, 1, tzinfo=UTC),
        failure_reason=None,
        trace_id=None,
    )
    cancel_run = CancelRunUseCase(store, clock=lambda: datetime(2026, 1, 2, tzinfo=UTC))

    view = cancel_run(created.run_id)

    assert view.status == RunStatus.SUCCEEDED
    assert view.cancel_requested_at == datetime(2026, 1, 2, tzinfo=UTC)


def test_cancel_run_missing_raises_run_not_found() -> None:
    store = FakeRunDeclarationStore()
    cancel_run = CancelRunUseCase(store)

    with pytest.raises(RunNotFound):
        cancel_run(uuid4())
