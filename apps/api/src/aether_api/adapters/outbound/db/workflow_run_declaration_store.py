"""spec 0005 2.3, 2.9 개정 2: `WorkflowRunDeclarationStore` 의 PostgreSQL 구현.

`connect` 는 연결 **팩토리**입니다(`PostgresRunDeclarationStore` 와 같은 패턴) — 메서드마다 새
연결을 열고 `with connect() as conn:` 이 커밋(성공 시)·롤백(예외 시)·닫기를 맡깁니다.
`aether_control` 역할로 접속하며 `control.workflow_runs` 만 다룹니다(실행 상태 정본인
`data.workflow_run_executions` 는 모릅니다, AR-7).

`create` 는 `(workflow_id, workflow_version)` 번호로 `control.workflow_versions` 에서 Version
행을 찾아 **한 INSERT … SELECT** 로 선언합니다 — Version 의 PK 를 호출부가 알 필요가 없고
(`WorkflowVersion` 값 객체에는 id 가 없습니다), 없는 Version 이면 행이 만들어지지 않습니다.
`get` 은 `control.workflow_runs` 를 `control.workflow_versions` 와 JOIN 해 `workflow_id`·
`version`(번호)을 채웁니다.

`apply_status` 는 **한 UPDATE** 로 `seq` 단조 증가 규칙을 원자적으로 적용합니다 —
`WHERE id = %s AND status_seq < %s`. 나머지 열은 `COALESCE(new, old)` 로 `None` 이 기존 값을
지우지 않게 합니다.

**예외 하나 — `waiting_run_id`.** 그 열은 `COALESCE` 로 두지 않고 **상태에서 유도**합니다:
`waiting_run` 일 때만 값이 있고 다른 상태로 가면 `NULL` 입니다. `COALESCE` 로 두면 기다림이
끝난 뒤에도 "무엇을 기다리는가" 가 남아(스트림이 값을 **지우는** 신호를 실을 수 없으므로)
`succeeded` 인 Run 이 자식 Run 을 기다리는 것처럼 보입니다. 지우는 신호를 계약에 더하는 대신
불변식으로 둡니다 — spec 2.3 이 대기를 상태로 가른 이유(D-2)가 그대로 근거입니다. 파킹이
실제로 생기는 PR B 가 이 불변식에 의존합니다.

같은 파라미터(`status`)를 **두 자리**에서 쓰므로 양쪽에 명시적 캐스트를 둡니다 — 하나는
enum 컬럼 대입, 하나는 `text` 비교라서 캐스트 없이는 PostgreSQL 이 파라미터 타입을 정하지
못하고 `AmbiguousParameter` 로 거부합니다(2026-10-14 실측).
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Any
from uuid import UUID

import psycopg
from aether_workflow.domain.run_status import WorkflowRunStatus
from psycopg.types.json import Jsonb

from aether_api.domain.workflow import WorkflowVersionNotFound
from aether_api.domain.workflow_run import WorkflowRunView

_SelectRow = tuple[
    UUID,  # workflow_run_id
    UUID,  # workflow_id
    int,  # workflow_version
    UUID,  # workflow_version_id
    str,  # status
    str | None,  # current_node_id
    UUID | None,  # waiting_run_id
    datetime,  # requested_at
    datetime | None,  # started_at
    datetime | None,  # finished_at
    str | None,  # failure_reason
]

_SELECT_COLUMNS = """
    r.id, v.workflow_id, v.version, r.workflow_version_id, r.status::text,
    r.current_node_id, r.waiting_run_id, r.requested_at, r.started_at, r.finished_at,
    r.failure_reason
"""

_FROM_JOIN = """
    FROM control.workflow_runs r
    JOIN control.workflow_versions v ON v.id = r.workflow_version_id
"""


def _row_to_view(row: _SelectRow) -> WorkflowRunView:
    (
        workflow_run_id,
        workflow_id,
        workflow_version,
        workflow_version_id,
        status,
        current_node_id,
        waiting_run_id,
        requested_at,
        started_at,
        finished_at,
        failure_reason,
    ) = row
    return WorkflowRunView(
        workflow_run_id=workflow_run_id,
        workflow_id=workflow_id,
        workflow_version=workflow_version,
        workflow_version_id=workflow_version_id,
        status=WorkflowRunStatus(status),
        current_node_id=current_node_id,
        waiting_run_id=waiting_run_id,
        requested_at=requested_at,
        started_at=started_at,
        finished_at=finished_at,
        failure_reason=failure_reason,
    )


class PostgresWorkflowRunDeclarationStore:
    """`control.workflow_runs` 에 대한 outbound 포트 `WorkflowRunDeclarationStore` 구현."""

    def __init__(self, connect: Callable[[], psycopg.Connection]) -> None:
        self._connect = connect

    def create(
        self, workflow_id: UUID, workflow_version: int, input: dict[str, Any] | None
    ) -> WorkflowRunView:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO control.workflow_runs (workflow_version_id, input)
                SELECT v.id, %s FROM control.workflow_versions v
                WHERE v.workflow_id = %s AND v.version = %s
                RETURNING id, workflow_version_id, status::text, requested_at
                """,
                (Jsonb(input) if input is not None else None, workflow_id, workflow_version),
            )
            row = cur.fetchone()
        if row is None:
            raise WorkflowVersionNotFound(workflow_id, workflow_version)
        workflow_run_id, workflow_version_id, status, requested_at = row
        return WorkflowRunView(
            workflow_run_id=workflow_run_id,
            workflow_id=workflow_id,
            workflow_version=workflow_version,
            workflow_version_id=workflow_version_id,
            status=WorkflowRunStatus(status),
            current_node_id=None,
            waiting_run_id=None,
            requested_at=requested_at,
            started_at=None,
            finished_at=None,
            failure_reason=None,
        )

    def get(self, workflow_run_id: UUID) -> WorkflowRunView | None:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                f"SELECT {_SELECT_COLUMNS} {_FROM_JOIN} WHERE r.id = %s", (workflow_run_id,)
            )
            row = cur.fetchone()
        if row is None:
            return None
        return _row_to_view(row)

    def apply_status(
        self,
        workflow_run_id: UUID,
        *,
        seq: int,
        status: WorkflowRunStatus,
        current_node_id: str | None,
        waiting_run_id: UUID | None,
        started_at: datetime | None,
        finished_at: datetime | None,
        failure_reason: str | None,
    ) -> bool:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                UPDATE control.workflow_runs
                SET status = %(status)s::control.workflow_run_status,
                    status_seq = %(seq)s,
                    current_node_id = COALESCE(%(current_node_id)s, current_node_id),
                    waiting_run_id = CASE
                        WHEN %(status)s::text = 'waiting_run'
                        THEN COALESCE(%(waiting_run_id)s, waiting_run_id)
                        ELSE NULL
                    END,
                    started_at = COALESCE(%(started_at)s, started_at),
                    finished_at = COALESCE(%(finished_at)s, finished_at),
                    failure_reason = COALESCE(%(failure_reason)s, failure_reason)
                WHERE id = %(workflow_run_id)s AND status_seq < %(seq)s
                RETURNING id
                """,
                {
                    "workflow_run_id": workflow_run_id,
                    "seq": seq,
                    "status": status.value,
                    "current_node_id": current_node_id,
                    "waiting_run_id": waiting_run_id,
                    "started_at": started_at,
                    "finished_at": finished_at,
                    "failure_reason": failure_reason,
                },
            )
            updated = cur.fetchone()
        return updated is not None
