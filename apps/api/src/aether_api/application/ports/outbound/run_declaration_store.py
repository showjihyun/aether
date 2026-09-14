"""spec 0002 2.1, 2.2, 2.4, 2.10, D-2, D-9, D-11: `control.runs` 에 대한 outbound 포트.

`RunDeclarationStore` 의 fake 구현(`apps/api/tests/fakes.py`)과 PostgreSQL 구현
(`adapters/outbound/db/run_declaration_store.py`)은 같은 포트 계약을 만족해야 합니다
(architecture.md 3.1 "TDD" 이득 — 포트 계약 테스트).

Control Plane 은 **선언만** 합니다(AR-7) — 이 포트는 `control.runs` 의 선언·투영 열만
다루고, 실행(`data.run_executions`, `data.run_states`)은 모릅니다.
"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol
from uuid import UUID

from aether_runtime.domain.failure import FailureReason
from aether_runtime.domain.run import RunStatus

from aether_api.domain.run import RunView


class RunDeclarationStore(Protocol):
    """`control.runs` 저장소 계약."""

    def create(
        self,
        agent_id: UUID,
        agent_version_id: UUID,
        agent_version: int,
        input: str,
        requested_by: UUID,
    ) -> RunView:
        """`status = queued` 로 새 선언 행을 만듭니다(spec 2.2). 커밋까지 이 호출 안에서
        끝납니다."""
        ...

    def get(self, run_id: UUID) -> RunView | None:
        """없으면 `None` — 유스케이스가 `RunNotFound` 로 바꿉니다(spec 0001 D-11)."""
        ...

    def request_cancel(self, run_id: UUID, at: datetime) -> RunView:
        """`cancel_requested_at` 이 비어 있으면 `at` 을 적고, 있으면 그대로 둡니다(멱등).

        없으면 `aether_api.domain.run.RunNotFound` 를 던집니다(spec 2.2, D-11).
        """
        ...

    def apply_status(
        self,
        run_id: UUID,
        *,
        seq: int,
        status: RunStatus,
        started_at: datetime | None,
        finished_at: datetime | None,
        failure_reason: FailureReason | None,
        trace_id: str | None,
    ) -> bool:
        """`seq` 가 저장된 `status_seq` 보다 클 때만 한 UPDATE 로 적용합니다(D-2).

        `started_at`/`finished_at`/`failure_reason`/`trace_id` 가 `None` 이면 기존 값을
        그대로 둡니다(`COALESCE(new, old)`). 적용됐으면 `True`, 아니면(낮거나 같은
        `seq`, 또는 없는 `run_id`) `False`.
        """
        ...
