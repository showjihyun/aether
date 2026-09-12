"""spec 0002 2.1, 2.4, 2.10, D-10: `RunStateStore` 의 PostgreSQL 구현.

`connect` 는 연결 **팩토리**(`Callable[[], psycopg.Connection]`)입니다 — `apps/api` 의
`PostgresApiKeyStore`(spec 0001 2.9 H-3)와 같은 패턴으로, 메서드마다 새 연결을 열고
`with connect() as conn:` 블록이 커밋(성공 시)·롤백(예외 시)·닫기를 전부 맡깁니다
(psycopg3 의 `Connection.__exit__`).

lease 는 **DB 시계**(`now()`) 하나만 기준으로 삼는 조건부 UPDATE 한 문장입니다 — 여러
worker 프로세스의 시계가 서로 달라도 경합은 항상 DB 가 판정합니다.
"""

from __future__ import annotations

from collections.abc import Callable
from uuid import UUID

import psycopg

from aether_runtime.domain.failure import FailureReason
from aether_runtime.domain.run import RunState, RunStatus


class PostgresRunStateStore:
    """`data.run_executions`(상태·lease)와 `data.run_states`(스냅숏)에 대한 PostgreSQL 구현."""

    def __init__(self, connect: Callable[[], psycopg.Connection]) -> None:
        self._connect = connect

    def load(self, run_id: UUID) -> RunState | None:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT state FROM data.run_states WHERE run_id = %s",
                (run_id,),
            )
            row = cur.fetchone()
        if row is None:
            return None
        return RunState.model_validate(row[0])

    def save(self, state: RunState) -> None:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO data.run_states (run_id, state, updated_at)
                VALUES (%s, %s, now())
                ON CONFLICT (run_id) DO UPDATE
                SET state = EXCLUDED.state, updated_at = now()
                """,
                (state.run_id, state.model_dump_json()),
            )

    def acquire_lease(self, run_id: UUID, owner: str, ttl_seconds: float) -> bool:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO data.run_executions (run_id, status)
                VALUES (%s, %s)
                ON CONFLICT (run_id) DO NOTHING
                """,
                (run_id, RunStatus.QUEUED.value),
            )
            cur.execute(
                """
                UPDATE data.run_executions
                SET lease_owner = %s, lease_until = now() + make_interval(secs => %s)
                WHERE run_id = %s AND (lease_until IS NULL OR lease_until < now())
                RETURNING run_id
                """,
                (owner, ttl_seconds, run_id),
            )
            row = cur.fetchone()
        return row is not None

    def renew_lease(self, run_id: UUID, owner: str, ttl_seconds: float) -> bool:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                UPDATE data.run_executions
                SET lease_until = now() + make_interval(secs => %s)
                WHERE run_id = %s AND lease_owner = %s
                RETURNING run_id
                """,
                (ttl_seconds, run_id, owner),
            )
            row = cur.fetchone()
        return row is not None

    def release(self, run_id: UUID, owner: str) -> None:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                UPDATE data.run_executions
                SET lease_owner = NULL, lease_until = NULL
                WHERE run_id = %s AND lease_owner = %s
                """,
                (run_id, owner),
            )

    def status(self, run_id: UUID) -> RunStatus | None:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT status FROM data.run_executions WHERE run_id = %s",
                (run_id,),
            )
            row = cur.fetchone()
        if row is None:
            return None
        return RunStatus(row[0])

    def set_status(
        self,
        run_id: UUID,
        status: RunStatus,
        *,
        failure_reason: FailureReason | None = None,
        trace_id: str | None = None,
    ) -> None:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO data.run_executions (run_id, status, failure_reason, trace_id)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (run_id) DO UPDATE
                SET status = EXCLUDED.status,
                    failure_reason = COALESCE(
                        EXCLUDED.failure_reason, data.run_executions.failure_reason
                    ),
                    trace_id = COALESCE(EXCLUDED.trace_id, data.run_executions.trace_id)
                """,
                (
                    run_id,
                    status.value,
                    failure_reason.value if failure_reason is not None else None,
                    trace_id,
                ),
            )
