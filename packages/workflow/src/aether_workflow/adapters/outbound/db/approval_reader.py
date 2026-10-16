"""spec 0005 2.6 개정 5 (3) (P4-4): `PostgresApprovalReader` - `ApprovalReader` 포트의 PostgreSQL
구현. **읽기만** 합니다.

`control.workflow_approvals` 를 SELECT 합니다. `aether_data` 에 이 표의 **SELECT 만** 더한 것이
마이그레이션 0008 이고 사람 검토 항목(H-1)입니다. 이 어댑터는 `approved_by`·`note` 를 읽지
않습니다 - 실행기가 필요한 것은 "이 노드 실행에 승인이 저장돼 있는가" 와 그 시각뿐이고, 승인 주체를
읽을 이유가 없습니다(권한 판정의 자리를 만들지 않습니다, C-4).

**일관된 승인만 믿습니다.** 승인 기록의 `workflow_run_id` 가 노드 실행
(`data.workflow_node_executions`, worker 가 소유하는 평면)이 속한 Run 과 같을 때만 승인으로
칩니다. api 는 지목한 노드 실행이 그 Run 이 기다리는 것일 때만 기록하므로 정상 경로에서는 항상
일치합니다 - 이 조건은 API 를 거치지 않고 잘못 심어진 행(다른 Run 의 id 로 기록된 승인)이
엉뚱한 Run 을 전진시키지 못하게 하는 두 번째 방어선입니다.
"""

from __future__ import annotations

from collections.abc import Callable
from uuid import UUID

import psycopg

from aether_workflow.domain.approval import Approval


class PostgresApprovalReader:
    def __init__(self, connect: Callable[[], psycopg.Connection]) -> None:
        self._connect = connect

    def approval_for(self, node_execution_id: UUID) -> Approval | None:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT a.node_execution_id, a.approved_at
                FROM control.workflow_approvals a
                JOIN data.workflow_node_executions n
                    ON n.id = a.node_execution_id AND n.workflow_run_id = a.workflow_run_id
                WHERE a.node_execution_id = %s
                """,
                (node_execution_id,),
            )
            row = cur.fetchone()
        if row is None:
            return None
        return Approval(node_execution_id=row[0], approved_at=row[1])
