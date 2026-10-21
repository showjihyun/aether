"""spec 0007 2.3, D-3, D-4 (P5-1): `WorkflowNodeStateProjectionStore` 의 PostgreSQL 구현.

`connect` 는 연결 팩토리입니다(`PostgresWorkflowRunDeclarationStore` 와 같은 패턴). `aether_control`
역할로 접속하며 `control.workflow_node_states` 만 다룹니다(`data` 는 모릅니다, AR-7).

`apply_status` 는 **한 문장**입니다: `INSERT … SELECT … FROM control.workflow_runs … ON CONFLICT
(workflow_run_id, node_id) DO UPDATE … WHERE status_seq < excluded.status_seq`.

- `SELECT … FROM control.workflow_runs` 라서 없는 Workflow Run 이면 행이 만들어지지 않고 FK 예외도
  나지 않습니다(`False`).
- `WHERE` 가 늦은(같거나 낮은) 메시지를 버립니다 - 키가 `(run, node)` 이므로 비교도 노드 단위입니다.
- `started_at` 은 `COALESCE(new, old)`, `finished_at`·`failure_reason` 은 메시지 값 그대로입니다
  (루프에서 노드가 다시 `running` 이 될 때 이전 회차의 종결 값이 남지 않게).
"""

from __future__ import annotations

import base64
from collections.abc import Callable
from uuid import UUID

import psycopg
from aether_workflow.domain.node_execution import NodeExecutionStatus

from aether_api.domain.cursor import InvalidCursor
from aether_api.domain.workflow_node_state import WorkflowNodeStatePage, WorkflowNodeStateView
from aether_api.domain.workflow_node_status_message import WorkflowNodeStatusMessage


def _encode_cursor(node_id: str) -> str:
    return base64.urlsafe_b64encode(node_id.encode("utf-8")).decode("ascii")


def _decode_cursor(cursor: str) -> str:
    try:
        node_id = base64.urlsafe_b64decode(cursor.encode("ascii")).decode("utf-8")
    except ValueError:  # base64·utf-8 해독 실패는 모두 ValueError 계열
        raise InvalidCursor(cursor) from None
    if not node_id:
        raise InvalidCursor(cursor)
    return node_id


class PostgresWorkflowNodeStateProjectionStore:
    def __init__(self, connect: Callable[[], psycopg.Connection]) -> None:
        self._connect = connect

    def apply_status(self, message: WorkflowNodeStatusMessage) -> bool:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO control.workflow_node_states AS t
                    (workflow_run_id, node_id, kind, status, status_seq,
                     started_at, finished_at, failure_reason)
                SELECT r.id, %(node_id)s, %(kind)s,
                       %(status)s, %(status_seq)s,
                       %(started_at)s, %(finished_at)s, %(failure_reason)s
                FROM control.workflow_runs r
                WHERE r.id = %(workflow_run_id)s
                ON CONFLICT (workflow_run_id, node_id) DO UPDATE
                SET kind = excluded.kind,
                    status = excluded.status,
                    status_seq = excluded.status_seq,
                    started_at = COALESCE(excluded.started_at, t.started_at),
                    finished_at = excluded.finished_at,
                    failure_reason = excluded.failure_reason
                WHERE t.status_seq < excluded.status_seq
                RETURNING t.workflow_run_id
                """,
                {
                    "workflow_run_id": message.workflow_run_id,
                    "node_id": message.node_id,
                    "kind": message.kind,
                    "status": message.status.value,
                    "status_seq": message.status_seq,
                    "started_at": message.started_at,
                    "finished_at": message.finished_at,
                    "failure_reason": message.failure_reason,
                },
            )
            applied = cur.fetchone()
        return applied is not None

    def list_for_run(
        self, workflow_run_id: UUID, limit: int, cursor: str | None
    ) -> WorkflowNodeStatePage:
        """`node_id` 오름차순 키셋 페이지(P5-2) - 노드당 한 행이라 안정적인 키입니다."""
        params: dict[str, object] = {"workflow_run_id": workflow_run_id, "limit": limit + 1}
        after = ""
        if cursor is not None:
            after = "AND node_id > %(after)s"
            params["after"] = _decode_cursor(cursor)
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT node_id, kind, status, started_at, finished_at, failure_reason
                FROM control.workflow_node_states
                WHERE workflow_run_id = %(workflow_run_id)s {after}
                ORDER BY node_id
                LIMIT %(limit)s
                """,
                params,
            )
            rows = cur.fetchall()
        items = [
            WorkflowNodeStateView(
                node_id=r[0],
                kind=r[1],
                status=NodeExecutionStatus(r[2]),
                started_at=r[3],
                finished_at=r[4],
                failure_reason=r[5],
            )
            for r in rows[:limit]
        ]
        next_cursor = _encode_cursor(items[-1].node_id) if len(rows) > limit else None
        return WorkflowNodeStatePage(items=items, next_cursor=next_cursor)
