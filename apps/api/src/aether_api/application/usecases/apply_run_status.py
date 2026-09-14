"""spec 0002 2.4, 2.18, D-2: `ApplyRunStatus` 포트의 구현 — 저장소에 그대로 위임합니다.

`seq` 단조 증가 규칙과 `COALESCE` 는 `RunDeclarationStore.apply_status` (한 UPDATE)가
소유합니다 — 이 유스케이스는 `RunStatusMessage` 를 저장소 시그니처로 펼칠 뿐입니다.
"""

from __future__ import annotations

from aether_api.application.ports.outbound.run_declaration_store import RunDeclarationStore
from aether_api.domain.run_status_message import RunStatusMessage


class ApplyRunStatusUseCase:
    """`RunDeclarationStore` 하나로 inbound 포트 `ApplyRunStatus` 를 구현합니다."""

    def __init__(self, store: RunDeclarationStore) -> None:
        self._store = store

    def __call__(self, message: RunStatusMessage) -> bool:
        return self._store.apply_status(
            message.run_id,
            seq=message.seq,
            status=message.status,
            started_at=message.started_at,
            finished_at=message.finished_at,
            failure_reason=message.failure_reason,
            trace_id=message.trace_id,
        )
