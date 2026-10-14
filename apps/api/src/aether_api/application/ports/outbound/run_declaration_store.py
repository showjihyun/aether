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

    def create_with_id(
        self, run_id: UUID, agent_version_id: UUID, input: str, requested_by: UUID | None
    ) -> bool:
        """주어진 `run_id` 로 선언 행을 만듭니다(`INSERT … ON CONFLICT (id) DO NOTHING`).

        새로 만들었으면 `True`, 이미 있었으면 `False`(멱등, spec 0005 2.5 개정 3). `requested_by`
        는 Workflow 를 시작한 주체를 그대로 물려받은 값입니다 — 비우면 `GET /runs/{id}` 가 500 이라
        사람 주체를 발명하지 않고 책임의 사슬을 잇습니다(없으면 NULL, 실행기는 그런 요청을 만들지
        않습니다). `agent_version_id` 가 없으면
        (FK 위반) 예외를 그대로 올립니다.
        """
        ...

    def get(self, run_id: UUID) -> RunView | None:
        """없으면 `None` — 유스케이스가 `RunNotFound` 로 바꿉니다(spec 0001 D-11)."""
        ...

    def status(self, run_id: UUID) -> RunStatus | None:
        """선언 행의 상태만 읽습니다. 없으면 `None`.

        `get` 과 나눈 이유(2026-10-14): `RunView` 는 `requested_by` 를 **필수**로 요구하는데
        Workflow 가 요청한 자식 Run 은 그 값이 비어 있을 수 있습니다. "이미 통지됐는가" 만
        알고 싶은 자리에서 전체 view 를 조립하면 그 자리에서 터집니다. 좁은 문을 둡니다.
        """
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
