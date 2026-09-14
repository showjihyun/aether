"""spec 0001 D-11, spec 0002 2.2: `GetRun` 포트의 구현 — 투영만 읽습니다.

`domain`·`application.ports` 만 import 합니다(AR-9).
"""

from __future__ import annotations

from uuid import UUID

from aether_api.application.ports.outbound.run_declaration_store import RunDeclarationStore
from aether_api.domain.run import RunNotFound, RunView


class GetRunUseCase:
    """`RunDeclarationStore` 하나로 inbound 포트 `GetRun` 을 구현합니다."""

    def __init__(self, store: RunDeclarationStore) -> None:
        self._store = store

    def __call__(self, run_id: UUID) -> RunView:
        view = self._store.get(run_id)
        if view is None:
            raise RunNotFound(run_id)
        return view
