"""spec 0006 2.3, D-3: `ListRuns` 포트의 구현 - 투영만 읽습니다(AR-9)."""

from __future__ import annotations

from aether_runtime.domain.run import RunStatus

from aether_api.application.ports.outbound.run_declaration_store import RunDeclarationStore
from aether_api.domain.run import RunPage


class ListRunsUseCase:
    """`RunDeclarationStore` 하나로 inbound 포트 `ListRuns` 를 구현합니다."""

    def __init__(self, store: RunDeclarationStore) -> None:
        self._store = store

    def __call__(self, limit: int, cursor: str | None, status: RunStatus | None) -> RunPage:
        return self._store.list(limit, cursor, status)
