"""spec 0002 2.2, D-11: `CancelRun` 포트의 구현 — 멱등, 종결이어도 현재 상태로 202.

`RunDeclarationStore.request_cancel` 이 `COALESCE` 로 멱등을 보장합니다 — 이 유스케이스는
"지금" 을 얻어 그대로 건네줄 뿐입니다. `clock` 은 테스트가 결정적으로 주입할 수 있는
자리입니다(spec 0002 R-11) — `apps/api/tests/fakes.py` 의 `_default_clock` 과 같은 패턴.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from uuid import UUID

from aether_api.application.ports.outbound.run_declaration_store import RunDeclarationStore
from aether_api.domain.run import RunView


def _default_clock() -> datetime:
    return datetime.now(UTC)


class CancelRunUseCase:
    """`RunDeclarationStore` 하나로 inbound 포트 `CancelRun` 을 구현합니다."""

    def __init__(
        self,
        store: RunDeclarationStore,
        clock: Callable[[], datetime] = _default_clock,
    ) -> None:
        self._store = store
        self._clock = clock

    def __call__(self, run_id: UUID) -> RunView:
        return self._store.request_cancel(run_id, self._clock())
