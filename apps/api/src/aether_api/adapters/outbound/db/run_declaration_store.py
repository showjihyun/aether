"""spec 0002 2.1, 2.2, 2.4, 2.10, D-2, D-9, D-11: `RunDeclarationStore` 의 PostgreSQL 구현.

`connect` 는 연결 **팩토리**입니다(`PostgresAgentRepository`·`PostgresApiKeyStore` 와
같은 패턴, spec 0001 H-3) — 메서드마다 새 연결을 열고 `with connect() as conn:` 이
커밋(성공 시)·롤백(예외 시)·닫기를 맡깁니다.

`get`/`request_cancel`/`create` 는 `control.runs` 를 `control.agent_versions` 와
JOIN 해 `agent_id`·`version`(int)을 함께 읽습니다 — `control.runs` 자신은
`agent_version_id`(FK) 만 가지고 있기 때문입니다(spec 2.10).

`apply_status` 는 **한 UPDATE** 로 `seq` 단조 증가 규칙(D-2)을 원자적으로 적용합니다 —
`WHERE id = %s AND (status_seq IS NULL OR status_seq < %s)`. 시각·사유·trace 는
`COALESCE(new, old)` 로 `None` 이 기존 값을 지우지 않게 합니다.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from uuid import UUID

import psycopg
from aether_runtime.domain.failure import FailureReason
from aether_runtime.domain.run import RunStatus

from aether_api.domain.run import RunNotFound, RunView

_SelectRow = tuple[
    UUID,  # run_id
    UUID,  # agent_id
    int,  # agent_version
    str,  # status
    datetime,  # requested_at
    UUID | None,  # requested_by
    datetime | None,  # started_at
    datetime | None,  # finished_at
    str | None,  # failure_reason
    str | None,  # trace_id
    datetime | None,  # cancel_requested_at
]

_SELECT_COLUMNS = """
    r.id, av.agent_id, av.version, r.status, r.requested_at, r.requested_by,
    r.started_at, r.finished_at, r.failure_reason, r.trace_id, r.cancel_requested_at
"""

_FROM_JOIN = """
    FROM control.runs r
    JOIN control.agent_versions av ON av.id = r.agent_version_id
"""


def _row_to_view(row: _SelectRow) -> RunView:
    (
        run_id,
        agent_id,
        agent_version,
        status,
        requested_at,
        requested_by,
        started_at,
        finished_at,
        failure_reason,
        trace_id,
        cancel_requested_at,
    ) = row
    if requested_by is None:  # pragma: no cover - api 는 항상 인증된 principal 로 만듭니다
        raise RuntimeError(f"control.runs {run_id} has no requested_by")
    return RunView(
        run_id=run_id,
        agent_id=agent_id,
        agent_version=agent_version,
        status=RunStatus(status),
        requested_at=requested_at,
        requested_by=requested_by,
        started_at=started_at,
        finished_at=finished_at,
        failure_reason=FailureReason(failure_reason) if failure_reason is not None else None,
        trace_id=trace_id,
        cancel_requested_at=cancel_requested_at,
    )


class PostgresRunDeclarationStore:
    """`control.runs` 에 대한 outbound 포트 `RunDeclarationStore` 의 PostgreSQL 구현."""

    def __init__(self, connect: Callable[[], psycopg.Connection]) -> None:
        self._connect = connect

    def create(
        self,
        agent_id: UUID,
        agent_version_id: UUID,
        agent_version: int,
        input: str,
        requested_by: UUID,
    ) -> RunView:
        """`agent_id`·`agent_version` 은 호출부(`RequestRunUseCase`)가 이미
        `AgentRepository` 로 확인한 값을 그대로 씁니다 — 이 INSERT 하나로 커밋까지
        끝나므로 삽입 직후 다시 JOIN 해 읽을 필요가 없습니다."""
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO control.runs (agent_version_id, input, requested_by)
                VALUES (%s, %s, %s)
                RETURNING id, status, requested_at
                """,
                (agent_version_id, input, requested_by),
            )
            row = cur.fetchone()
        if row is None:  # pragma: no cover - INSERT ... RETURNING always yields a row
            raise RuntimeError("INSERT ... RETURNING control.runs returned no row")
        run_id, status, requested_at = row
        return RunView(
            run_id=run_id,
            agent_id=agent_id,
            agent_version=agent_version,
            status=RunStatus(status),
            requested_at=requested_at,
            requested_by=requested_by,
            started_at=None,
            finished_at=None,
            failure_reason=None,
            trace_id=None,
            cancel_requested_at=None,
        )

    def get(self, run_id: UUID) -> RunView | None:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(f"SELECT {_SELECT_COLUMNS} {_FROM_JOIN} WHERE r.id = %s", (run_id,))
            row = cur.fetchone()
        if row is None:
            return None
        return _row_to_view(row)

    def request_cancel(self, run_id: UUID, at: datetime) -> RunView:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                UPDATE control.runs
                SET cancel_requested_at = COALESCE(cancel_requested_at, %s)
                WHERE id = %s
                RETURNING id
                """,
                (at, run_id),
            )
            updated = cur.fetchone()
            if updated is None:
                raise RunNotFound(run_id)

            cur.execute(f"SELECT {_SELECT_COLUMNS} {_FROM_JOIN} WHERE r.id = %s", (run_id,))
            row = cur.fetchone()
        if row is None:  # pragma: no cover - 방금 갱신한 행입니다
            raise RuntimeError(f"control.runs {run_id} not found immediately after update")
        return _row_to_view(row)

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
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                UPDATE control.runs
                SET status = %(status)s,
                    status_seq = %(seq)s,
                    started_at = COALESCE(%(started_at)s, started_at),
                    finished_at = COALESCE(%(finished_at)s, finished_at),
                    failure_reason = COALESCE(%(failure_reason)s, failure_reason),
                    trace_id = COALESCE(%(trace_id)s, trace_id)
                WHERE id = %(run_id)s AND (status_seq IS NULL OR status_seq < %(seq)s)
                RETURNING id
                """,
                {
                    "run_id": run_id,
                    "seq": seq,
                    "status": status.value,
                    "started_at": started_at,
                    "finished_at": finished_at,
                    "failure_reason": failure_reason.value if failure_reason is not None else None,
                    "trace_id": trace_id,
                },
            )
            updated = cur.fetchone()
        return updated is not None
