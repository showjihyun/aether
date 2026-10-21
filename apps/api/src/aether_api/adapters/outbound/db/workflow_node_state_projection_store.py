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

from collections.abc import Callable

import psycopg

from aether_api.domain.workflow_node_status_message import WorkflowNodeStatusMessage


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
