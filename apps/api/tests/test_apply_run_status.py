"""spec 0002 2.4, 2.18, D-2: `ApplyRunStatusUseCase` — `seq` 단조 증가로 멱등 투영.

낮은/같은 `seq` 는 무시(적용 안 됨), 높은 `seq` 는 적용, `None` 필드는 기존 값을
유지합니다(`COALESCE(new, old)`).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from aether_api.application.usecases.apply_run_status import ApplyRunStatusUseCase
from aether_api.domain.run import RunView
from aether_api.domain.run_status_message import RunStatusMessage
from aether_runtime.domain.failure import FailureReason
from aether_runtime.domain.run import RunStatus

from apps.api.tests.fakes import FakeRunDeclarationStore


def _get(store: FakeRunDeclarationStore, run_id: UUID) -> RunView:
    view = store.get(run_id)
    assert view is not None
    return view


def _message(run_id: UUID, **overrides: Any) -> RunStatusMessage:
    payload: dict[str, Any] = {
        "run_id": run_id,
        "seq": 1,
        "status": RunStatus.RUNNING,
        "at": datetime(2026, 1, 1, tzinfo=UTC),
    }
    payload.update(overrides)
    return RunStatusMessage.model_validate(payload)


def test_higher_seq_is_applied() -> None:
    store = FakeRunDeclarationStore()
    created = store.create(uuid4(), uuid4(), 1, "x", uuid4())
    apply_status = ApplyRunStatusUseCase(store)

    applied = apply_status(_message(created.run_id, seq=1, status=RunStatus.RUNNING))

    assert applied is True
    assert _get(store, created.run_id).status == RunStatus.RUNNING


def test_lower_seq_is_ignored() -> None:
    store = FakeRunDeclarationStore()
    created = store.create(uuid4(), uuid4(), 1, "x", uuid4())
    apply_status = ApplyRunStatusUseCase(store)
    apply_status(_message(created.run_id, seq=5, status=RunStatus.RUNNING))

    applied = apply_status(_message(created.run_id, seq=3, status=RunStatus.WAITING))

    assert applied is False
    assert _get(store, created.run_id).status == RunStatus.RUNNING


def test_same_seq_is_ignored() -> None:
    store = FakeRunDeclarationStore()
    created = store.create(uuid4(), uuid4(), 1, "x", uuid4())
    apply_status = ApplyRunStatusUseCase(store)
    apply_status(_message(created.run_id, seq=5, status=RunStatus.RUNNING))

    applied = apply_status(_message(created.run_id, seq=5, status=RunStatus.WAITING))

    assert applied is False
    assert _get(store, created.run_id).status == RunStatus.RUNNING


def test_none_fields_keep_the_existing_value() -> None:
    store = FakeRunDeclarationStore()
    created = store.create(uuid4(), uuid4(), 1, "x", uuid4())
    apply_status = ApplyRunStatusUseCase(store)
    started_at = datetime(2026, 1, 1, tzinfo=UTC)
    apply_status(_message(created.run_id, seq=1, status=RunStatus.RUNNING, started_at=started_at))

    apply_status(_message(created.run_id, seq=2, status=RunStatus.WAITING))

    view = _get(store, created.run_id)
    assert view.status == RunStatus.WAITING
    assert view.started_at == started_at  # 두 번째 메시지의 started_at=None 이 지우지 않습니다.


def test_finished_seq_sets_finished_at_and_failure_reason() -> None:
    store = FakeRunDeclarationStore()
    created = store.create(uuid4(), uuid4(), 1, "x", uuid4())
    apply_status = ApplyRunStatusUseCase(store)
    finished_at = datetime(2026, 1, 1, 0, 5, tzinfo=UTC)

    apply_status(
        _message(
            created.run_id,
            seq=3,
            status=RunStatus.FAILED,
            finished_at=finished_at,
            failure_reason=FailureReason.MODEL_ERROR,
            trace_id="trace-abc",
        )
    )

    view = _get(store, created.run_id)
    assert view.status == RunStatus.FAILED
    assert view.finished_at == finished_at
    assert view.failure_reason == FailureReason.MODEL_ERROR
    assert view.trace_id == "trace-abc"
