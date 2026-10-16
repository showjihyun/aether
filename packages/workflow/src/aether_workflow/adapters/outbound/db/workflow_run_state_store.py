"""spec 0005 2.9 개정 2: `WorkflowRunStateStore` 의 PostgreSQL 구현 -
`data.workflow_run_executions`(상태·lease)와 `data.workflow_node_executions`(노드 실행 기록).

`connect` 는 연결 **팩토리**입니다(`PostgresRunStateStore` 와 같은 패턴) - 메서드마다 새 연결을
열고 `with connect() as conn:` 이 커밋(성공 시)·롤백(예외 시)·닫기를 맡깁니다. `aether_data`
역할로 접속합니다(마이그레이션 0005·0006 GRANT).

lease 는 **DB 시계**(`now()`) 하나만 기준으로 삼는 조건부 UPDATE 한 문장입니다 - 여러 worker
프로세스의 시계가 달라도 경합은 DB 가 판정합니다. `start_node` 는 `INSERT … ON CONFLICT DO
NOTHING RETURNING id` 라서 같은 `(workflow_run_id, node_id, iteration)` 를 두 번째로 시작하면
행이 돌아오지 않고 `None` 입니다 - 그것이 멱등·재개의 축입니다.

`status` 열은 `control.workflow_run_status` enum 이라 text 파라미터에 명시적 캐스트
(`%s::control.workflow_run_status`)를 둡니다. 노드 실행의 `status` 도 마찬가지로
`data.workflow_node_execution_status`(마이그레이션 0007)입니다.

`park_node` 는 자식 Run 의 id 와 `waiting_run` 을 **한 UPDATE** 로 영속합니다 - 발사 전에 부릅니다.
`set_status` 의 `waiting_run_id` 는 `COALESCE` 가 아니라 **상태에서 유도**합니다(`waiting_run` 일
때만 값이 있고 주지 않으면 이전 값, 다른 상태로 가면 NULL) - api 의 투영(`apply_status`)과 같은
불변식입니다. `waiting_node_execution_id` 도 같은 규칙입니다(`waiting_approval` 일 때만 값이 있고
주지
않으면 이전 값, 다른 상태로 가면 NULL - P4-4). `wake_at`(`WAIT` 가 깨어날 시각, P4-3)도 같은
규칙이고 `waiting_timer` 일 때만 값이 있습니다. 이 어댑터의 어떤 메서드도 파킹 때문에 lease 열을
새로
쓰지 않습니다: lease 를 놓는
것은 `release` 하나이고 호출자의 `finally` 가 부릅니다(R-7).
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from uuid import UUID

import psycopg
from psycopg.types.json import Jsonb

from aether_workflow.domain.failure import WorkflowFailureReason
from aether_workflow.domain.node_execution import NodeExecutionRecord, NodeExecutionStatus
from aether_workflow.domain.node_output import NodeOutput
from aether_workflow.domain.run_execution import WorkflowRunExecution
from aether_workflow.domain.run_status import WorkflowRunStatus


class PostgresWorkflowRunStateStore:
    def __init__(self, connect: Callable[[], psycopg.Connection]) -> None:
        self._connect = connect

    def acquire_lease(self, workflow_run_id: UUID, owner: str, ttl_seconds: float) -> bool:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO data.workflow_run_executions (workflow_run_id, status)
                VALUES (%s, 'queued')
                ON CONFLICT (workflow_run_id) DO NOTHING
                """,
                (workflow_run_id,),
            )
            cur.execute(
                """
                UPDATE data.workflow_run_executions
                SET lease_owner = %s,
                    lease_until = now() + make_interval(secs => %s),
                    updated_at = now()
                WHERE workflow_run_id = %s AND (lease_until IS NULL OR lease_until < now())
                RETURNING workflow_run_id
                """,
                (owner, ttl_seconds, workflow_run_id),
            )
            row = cur.fetchone()
        return row is not None

    def renew_lease(self, workflow_run_id: UUID, owner: str, ttl_seconds: float) -> bool:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                UPDATE data.workflow_run_executions
                SET lease_until = now() + make_interval(secs => %s), updated_at = now()
                WHERE workflow_run_id = %s AND lease_owner = %s
                RETURNING workflow_run_id
                """,
                (ttl_seconds, workflow_run_id, owner),
            )
            row = cur.fetchone()
        return row is not None

    def release(self, workflow_run_id: UUID, owner: str) -> None:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                UPDATE data.workflow_run_executions
                SET lease_owner = NULL, lease_until = NULL, updated_at = now()
                WHERE workflow_run_id = %s AND lease_owner = %s
                """,
                (workflow_run_id, owner),
            )

    def load(self, workflow_run_id: UUID) -> WorkflowRunExecution | None:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT status::text, status_seq, current_node_id, started_at, finished_at,
                       failure_reason, waiting_run_id, waiting_node_execution_id, wake_at
                FROM data.workflow_run_executions
                WHERE workflow_run_id = %s
                """,
                (workflow_run_id,),
            )
            row = cur.fetchone()
        if row is None:
            return None
        (
            status,
            status_seq,
            current_node_id,
            started_at,
            finished_at,
            failure_reason,
            waiting_run_id,
            waiting_node_execution_id,
            wake_at,
        ) = row
        return WorkflowRunExecution(
            workflow_run_id=workflow_run_id,
            status=WorkflowRunStatus(status),
            status_seq=status_seq,
            current_node_id=current_node_id,
            started_at=started_at,
            finished_at=finished_at,
            failure_reason=failure_reason,
            waiting_run_id=waiting_run_id,
            waiting_node_execution_id=waiting_node_execution_id,
            wake_at=wake_at,
        )

    def set_status(
        self,
        workflow_run_id: UUID,
        status: WorkflowRunStatus,
        *,
        seq: int,
        current_node_id: str | None = None,
        failure_reason: WorkflowFailureReason | None = None,
        started_at: datetime | None = None,
        finished_at: datetime | None = None,
        waiting_run_id: UUID | None = None,
        waiting_node_execution_id: UUID | None = None,
        wake_at: datetime | None = None,
    ) -> None:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                UPDATE data.workflow_run_executions
                SET status = %(status)s::control.workflow_run_status,
                    status_seq = %(seq)s,
                    current_node_id = COALESCE(%(current_node_id)s, current_node_id),
                    failure_reason = COALESCE(%(failure_reason)s, failure_reason),
                    waiting_run_id = CASE
                        WHEN %(status)s::text = 'waiting_run'
                        THEN COALESCE(%(waiting_run_id)s, waiting_run_id)
                        ELSE NULL
                    END,
                    waiting_node_execution_id = CASE
                        WHEN %(status)s::text = 'waiting_approval'
                        THEN COALESCE(%(waiting_node_execution_id)s, waiting_node_execution_id)
                        ELSE NULL
                    END,
                    wake_at = CASE
                        WHEN %(status)s::text = 'waiting_timer'
                        THEN COALESCE(%(wake_at)s, wake_at)
                        ELSE NULL
                    END,
                    started_at = COALESCE(%(started_at)s, started_at),
                    finished_at = COALESCE(%(finished_at)s, finished_at),
                    updated_at = now()
                WHERE workflow_run_id = %(workflow_run_id)s
                RETURNING workflow_run_id
                """,
                {
                    "workflow_run_id": workflow_run_id,
                    "status": status.value,
                    "seq": seq,
                    "current_node_id": current_node_id,
                    "failure_reason": failure_reason.value if failure_reason else None,
                    "waiting_run_id": waiting_run_id,
                    "waiting_node_execution_id": waiting_node_execution_id,
                    "wake_at": wake_at,
                    "started_at": started_at,
                    "finished_at": finished_at,
                },
            )
            row = cur.fetchone()
        if row is None:
            raise RuntimeError(f"no execution row for workflow run {workflow_run_id}")

    def start_node(self, workflow_run_id: UUID, node_id: str, iteration: int) -> UUID | None:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO data.workflow_node_executions
                    (workflow_run_id, node_id, iteration, status)
                VALUES (%s, %s, %s, %s::data.workflow_node_execution_status)
                ON CONFLICT (workflow_run_id, node_id, iteration) DO NOTHING
                RETURNING id
                """,
                (workflow_run_id, node_id, iteration, NodeExecutionStatus.RUNNING.value),
            )
            row = cur.fetchone()
        if row is None:
            return None
        node_execution_id: UUID = row[0]
        return node_execution_id

    def park_node(self, node_execution_id: UUID, agent_run_id: UUID) -> None:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                UPDATE data.workflow_node_executions
                SET status = 'waiting_run'::data.workflow_node_execution_status,
                    agent_run_id = %s
                WHERE id = %s
                """,
                (agent_run_id, node_execution_id),
            )

    def park_node_for_approval(self, node_execution_id: UUID) -> None:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                UPDATE data.workflow_node_executions
                SET status = 'waiting_approval'::data.workflow_node_execution_status
                WHERE id = %s
                """,
                (node_execution_id,),
            )

    def park_node_for_timer(self, node_execution_id: UUID) -> None:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                UPDATE data.workflow_node_executions
                SET status = 'waiting_timer'::data.workflow_node_execution_status
                WHERE id = %s
                """,
                (node_execution_id,),
            )

    def finish_node(
        self,
        node_execution_id: UUID,
        status: NodeExecutionStatus,
        finished_at: datetime,
        failure_reason: WorkflowFailureReason | None = None,
        output: NodeOutput | None = None,
    ) -> None:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                UPDATE data.workflow_node_executions
                SET status = %(status)s::data.workflow_node_execution_status,
                    finished_at = %(finished_at)s,
                    failure_reason = COALESCE(%(failure_reason)s, failure_reason),
                    output = COALESCE(%(output)s::jsonb, output),
                    output_truncated = CASE WHEN %(output)s::jsonb IS NULL
                        THEN output_truncated ELSE %(truncated)s END
                WHERE id = %(id)s
                """,
                {
                    "status": status.value,
                    "finished_at": finished_at,
                    "failure_reason": failure_reason.value if failure_reason is not None else None,
                    "output": Jsonb(output.value) if output is not None else None,
                    "truncated": output.truncated if output is not None else False,
                    "id": node_execution_id,
                },
            )

    def node_executions(self, workflow_run_id: UUID) -> tuple[NodeExecutionRecord, ...]:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, node_id, iteration, status::text, started_at, finished_at,
                       agent_run_id, failure_reason, output, output_truncated
                FROM data.workflow_node_executions
                WHERE workflow_run_id = %s
                ORDER BY started_at, node_id, iteration
                """,
                (workflow_run_id,),
            )
            rows = cur.fetchall()
        return tuple(
            NodeExecutionRecord(
                id=row[0],
                workflow_run_id=workflow_run_id,
                node_id=row[1],
                iteration=row[2],
                status=NodeExecutionStatus(row[3]),
                started_at=row[4],
                finished_at=row[5],
                agent_run_id=row[6],
                failure_reason=row[7],
                output=row[8],
                output_truncated=row[9],
            )
            for row in rows
        )
