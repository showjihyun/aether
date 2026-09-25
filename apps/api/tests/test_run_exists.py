"""spec 0002 2.2, 2.7(AD-2 결함 수정): `RunExistsUseCase` — 존재만 확인합니다.

`FakeRunDeclarationStore` 로, 컨테이너 없이(AR-9). 이 유스케이스는
`ReadRunEventsUseCase`·`GetRunUseCase` 와 같은 `RunDeclarationStore` 를 씁니다 — 새
outbound 포트를 만들지 않습니다.
"""

from __future__ import annotations

from uuid import uuid4

from aether_api.application.usecases.run_exists import RunExistsUseCase

from apps.api.tests.fakes import FakeRunDeclarationStore


def test_run_exists_returns_true_for_a_stored_run() -> None:
    store = FakeRunDeclarationStore()
    created = store.create(uuid4(), uuid4(), 1, "do it", uuid4())
    run_exists = RunExistsUseCase(store)

    assert run_exists(created.run_id) is True


def test_run_exists_returns_false_for_a_missing_run() -> None:
    store = FakeRunDeclarationStore()
    run_exists = RunExistsUseCase(store)

    assert run_exists(uuid4()) is False
