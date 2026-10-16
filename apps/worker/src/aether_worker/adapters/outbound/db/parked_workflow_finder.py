"""spec 0005 2.5 개정 3 (P4-2a B2): `PostgresParkedWorkflowFinder` - `ParkedWorkflowFinder` 의
PostgreSQL 구현. **읽기만** 합니다(P4-2a 는 새 GRANT 가 없었고, 승인 대기를 줍는 P4-4 는
마이그레이션 0008 의 `control.workflow_approvals` SELECT 하나를 씁니다).

- `data.workflow_run_executions` - 파킹 여부와 기다리는 대상. worker 가 소유하는 평면입니다.
- `data.run_executions` - 자식 Run 의 실행 상태 정본. `control.runs` 의 투영(api 가 상태 스트림으로
  갱신)을 기다리지 않습니다 - 투영은 늦거나 유실될 수 있고 스위퍼는 바로 그 유실을 구하는
  장치입니다.
- `control.workflow_runs` - 재큐에 필요한 `workflow_version_id` (`aether_data` 는 SELECT 가
있습니다, 0005).
- `control.workflow_approvals` - 승인 대기를 줍는 근거(P4-4). **SELECT 만** 가집니다(0008, 사람
  검토 항목 H-1).

`ready_to_resume` 은 한 번의 SQL(JOIN)입니다. `waiting_run` 은 자식이 종결인 건을,
`waiting_approval` 은 **기다리는 그 노드 실행의 승인이 이미 저장된** 건을 줍습니다
(`UNION ALL`). 승인 뒤 재큐(XADD)가 유실돼도 Workflow 가 영원히 멈추지 않게 하는
안전망입니다 - 이벤트만 믿지 않습니다(`improvement-log/2026-10-11-001`). 지목 대상이
비어 있으면 어떤 승인도 근거가 되지 못합니다.

자식의 종결 집합(`succeeded`·`failed`·`cancelled`·`timed_out`)은
`aether_runtime.domain.run` 의 것과 같아야 하므로 SQL 에 상수로 쓰지 않고 도메인에서
받아 파라미터로 넘깁니다.
"""

from __future__ import annotations

from collections.abc import Callable
from uuid import UUID

import psycopg
from aether_runtime.domain.run import RunStatus, is_terminal

from aether_worker.application.ports.outbound.parked_workflow_finder import ParkedWorkflow

_TERMINAL = tuple(sorted(s.value for s in RunStatus if is_terminal(s)))


class PostgresParkedWorkflowFinder:
    def __init__(self, connect: Callable[[], psycopg.Connection]) -> None:
        self._connect = connect

    def waiting_on(self, agent_run_id: UUID) -> tuple[ParkedWorkflow, ...]:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT w.workflow_run_id, r.workflow_version_id
                FROM data.workflow_run_executions w
                JOIN control.workflow_runs r ON r.id = w.workflow_run_id
                WHERE w.status = 'waiting_run' AND w.waiting_run_id = %s
                """,
                (agent_run_id,),
            )
            rows = cur.fetchall()
        return tuple(ParkedWorkflow(workflow_run_id=r[0], workflow_version_id=r[1]) for r in rows)

    def ready_to_resume(self) -> tuple[ParkedWorkflow, ...]:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT workflow_run_id, workflow_version_id FROM (
                    SELECT w.workflow_run_id, r.workflow_version_id, w.updated_at
                    FROM data.workflow_run_executions w
                    JOIN control.workflow_runs r ON r.id = w.workflow_run_id
                    JOIN data.run_executions c ON c.run_id = w.waiting_run_id
                    WHERE w.status = 'waiting_run' AND c.status::text = ANY(%s)
                    UNION ALL
                    SELECT w.workflow_run_id, r.workflow_version_id, w.updated_at
                    FROM data.workflow_run_executions w
                    JOIN control.workflow_runs r ON r.id = w.workflow_run_id
                    JOIN control.workflow_approvals a
                        ON a.workflow_run_id = w.workflow_run_id
                       AND a.node_execution_id = w.waiting_node_execution_id
                    WHERE w.status = 'waiting_approval'
                ) ready
                ORDER BY updated_at
                """,
                (list(_TERMINAL),),
            )
            rows = cur.fetchall()
        return tuple(ParkedWorkflow(workflow_run_id=r[0], workflow_version_id=r[1]) for r in rows)
