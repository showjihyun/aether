"""spec 0001 D-11, spec 0002 2.2: `GetRunUseCase` — 투영만 읽습니다."""

from __future__ import annotations

from uuid import uuid4

import pytest
from aether_api.application.usecases.get_run import GetRunUseCase
from aether_api.domain.run import RunNotFound

from apps.api.tests.fakes import FakeRunDeclarationStore


def test_get_run_returns_the_stored_view() -> None:
    store = FakeRunDeclarationStore()
    created = store.create(uuid4(), uuid4(), 1, "do it", uuid4())
    get_run = GetRunUseCase(store)

    view = get_run(created.run_id)

    assert view == created


def test_get_run_missing_raises_run_not_found() -> None:
    store = FakeRunDeclarationStore()
    get_run = GetRunUseCase(store)

    with pytest.raises(RunNotFound):
        get_run(uuid4())
