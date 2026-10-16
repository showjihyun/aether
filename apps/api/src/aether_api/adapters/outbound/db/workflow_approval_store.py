"""spec 0005 2.6 개정 5, 2.9 (P4-4): `WorkflowApprovalStore` 의 PostgreSQL 구현.

`connect` 는 연결 **팩토리**입니다(`PostgresWorkflowRunDeclarationStore` 와 같은
패턴). `aether_control` 역할로 접속하며 `control.workflow_approvals` 만 다룹니다.
**append-only** 입니다: INSERT 와 SELECT 뿐이고 UPDATE·DELETE 를 시도하지 않습니다
(트리거가 막습니다, 0005).

`record` 는 `unique(workflow_run_id, node_execution_id)`(0008)를 어기면 `AlreadyApproved` 로
바꿉니다 - 동시에 들어온 두 요청 중 하나만 기록됩니다(유스케이스의 사전 검사는 경쟁을 막지 못하고
DB 제약이 막습니다). `approved_by` 는 호출자가 건넨 문자열을 **그대로** 적습니다.
"""

from __future__ import annotations

from collections.abc import Callable
from uuid import UUID

import psycopg
from psycopg import errors

from aether_api.domain.workflow_approval import AlreadyApproved, WorkflowApprovalView

_COLUMNS = "workflow_run_id, node_execution_id, approved_by, approved_at, note"


class PostgresWorkflowApprovalStore:
    def __init__(self, connect: Callable[[], psycopg.Connection]) -> None:
        self._connect = connect

    def record(
        self, workflow_run_id: UUID, node_execution_id: UUID, approved_by: str, note: str | None
    ) -> WorkflowApprovalView:
        try:
            with self._connect() as conn, conn.cursor() as cur:
                cur.execute(
                    f"""
                    INSERT INTO control.workflow_approvals
                        (workflow_run_id, node_execution_id, approved_by, note)
                    VALUES (%s, %s, %s, %s)
                    RETURNING {_COLUMNS}
                    """,
                    (workflow_run_id, node_execution_id, approved_by, note),
                )
                row = cur.fetchone()
        except errors.UniqueViolation:
            raise AlreadyApproved(workflow_run_id, node_execution_id) from None
        assert row is not None
        return _view(row)

    def get(self, workflow_run_id: UUID, node_execution_id: UUID) -> WorkflowApprovalView | None:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT {_COLUMNS} FROM control.workflow_approvals
                WHERE workflow_run_id = %s AND node_execution_id = %s
                """,
                (workflow_run_id, node_execution_id),
            )
            row = cur.fetchone()
        return None if row is None else _view(row)

    def list_for(self, workflow_run_id: UUID) -> tuple[WorkflowApprovalView, ...]:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT {_COLUMNS} FROM control.workflow_approvals
                WHERE workflow_run_id = %s ORDER BY approved_at, id
                """,
                (workflow_run_id,),
            )
            rows = cur.fetchall()
        return tuple(_view(row) for row in rows)


def _view(row: tuple[object, ...]) -> WorkflowApprovalView:
    run_id, node_execution_id, approved_by, approved_at, note = row
    assert isinstance(run_id, UUID) and isinstance(node_execution_id, UUID)
    assert isinstance(approved_by, str)
    return WorkflowApprovalView(
        workflow_run_id=run_id,
        node_execution_id=node_execution_id,
        approved_by=approved_by,
        approved_at=approved_at,  # type: ignore[arg-type]
        note=note if isinstance(note, str) else None,
    )
