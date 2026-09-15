"""spec 0002 2.7, D-4, R-3, R-8: `ReadRunEvents` 포트의 구현.

run 이 없으면 `RunNotFound`. 스트림이 없고 run 이 이미 종결이면 합성 `run.finished`
이벤트 하나만 내고 닫습니다(TTL 뒤 늦게 온 독자, 또는 발행 전 crash — 2.4 의
재발행이 곧 채우지만 기다리지 않습니다, 2.7 "스트림이 없을 때"). 그 외에는
`RunEventReader.read` 를 그대로 이어(재개는 `after_seq`), `run.finished` 를 만나면
닫습니다 — worker 는 이 유스케이스를 모릅니다(AR-7).

합성 이벤트의 `seq`: `RunDeclarationStore.get()` 이 돌려주는 `RunView` 는 내부
`status_seq` 부기(P1-5b `apply_status` 의 멱등 판정용)를 노출하지 않습니다 — 이
포트에 필드를 더하는 것은 이 단위(P1-6)의 파일 범위 밖입니다(`GET /runs/{id}`
응답 계약을 흔들 위험도 있습니다). 그래서 합성 이벤트는 항상 `seq=1` 을 씁니다 —
이 스트림에서 유일한 이벤트이므로 로컬로는 일관됩니다(구현 보고 "보고할 불일치"에
`status_seq` 노출이 필요해지면 후속 변경이 필요하다고 적습니다).
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from datetime import UTC, datetime
from uuid import UUID

from aether_runtime.domain.events import RunEvent
from aether_runtime.domain.run import RunStatus

from aether_api.application.ports.outbound.run_declaration_store import RunDeclarationStore
from aether_api.application.ports.outbound.run_event_reader import RunEventReader
from aether_api.domain.run import RunNotFound

_TERMINAL_STATUSES: frozenset[RunStatus] = frozenset(
    {RunStatus.SUCCEEDED, RunStatus.FAILED, RunStatus.CANCELLED, RunStatus.TIMED_OUT}
)
_DEFAULT_BLOCK_MS = 5_000
_SYNTHETIC_SEQ = 1


def _default_clock() -> datetime:
    return datetime.now(UTC)


class ReadRunEventsUseCase:
    """`RunEventReader` + `RunDeclarationStore` 로 inbound 포트 `ReadRunEvents` 를
    구현합니다. `domain`·`application.ports` 만 import 합니다(AR-9)."""

    def __init__(
        self,
        reader: RunEventReader,
        runs: RunDeclarationStore,
        *,
        block_ms: int = _DEFAULT_BLOCK_MS,
        clock: Callable[[], datetime] = _default_clock,
    ) -> None:
        self._reader = reader
        self._runs = runs
        self._block_ms = block_ms
        self._clock = clock

    async def __call__(self, run_id: UUID, after_seq: int | None) -> AsyncIterator[RunEvent]:
        run = self._runs.get(run_id)
        if run is None:
            raise RunNotFound(run_id)

        if run.status in _TERMINAL_STATUSES and not await self._reader.stream_exists(run_id):
            yield RunEvent(
                run_id=run_id,
                seq=_SYNTHETIC_SEQ,
                at=self._clock(),
                type="run.finished",
                payload={"status": run.status.value},
            )
            return

        async for event in self._reader.read(run_id, after_seq, self._block_ms):
            yield event
            if event.type == "run.finished":
                return
