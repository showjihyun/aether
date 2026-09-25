"""spec 0002 2.2, 2.7(AD-2 결함 수정): `RunExists` 포트의 구현.

`domain`·`application.ports` 만 import 합니다(AR-9). 기존 `RunDeclarationStore`
(`ReadRunEventsUseCase`·`GetRunUseCase` 가 쓰는 것과 같은 outbound 포트)로 조회만
하고, 새 outbound 포트는 만들지 않습니다.
"""

from __future__ import annotations

from uuid import UUID

from aether_api.application.ports.outbound.run_declaration_store import RunDeclarationStore


class RunExistsUseCase:
    """`RunDeclarationStore` 하나로 inbound 포트 `RunExists` 를 구현합니다."""

    def __init__(self, store: RunDeclarationStore) -> None:
        self._store = store

    def __call__(self, run_id: UUID) -> bool:
        return self._store.get(run_id) is not None
