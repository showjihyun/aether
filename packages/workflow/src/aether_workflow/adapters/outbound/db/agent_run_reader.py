"""spec 0005 2.5 개정 3, 2.9 개정 2 (P4-2a B2): `PostgresAgentRunReader` - `AgentRunReader` 포트의
PostgreSQL 구현. **읽기만** 합니다.

- 자식 Run 의 상태: `data.run_executions`(worker 가 소유하는 평면, `aether_data` 전부).
`control.runs`
  의 투영(api 가 상태 스트림으로 갱신)을 기다리지 않습니다 - 투영은 늦거나 유실될 수 있고, 이 읽기가
  스위퍼의 판정 근거입니다.
- Agent Version: `control.agent_versions`(`aether_data` 는 SELECT 가 있습니다, 0001).

`version_for(agent_id, None)` 은 그 Agent 의 **최대 version** 입니다.
`control.agents.current_version`
은 worker 가 읽을 수 없고(SELECT 없음), Version 은 append-only(불변 트리거, 0001)이므로 최대 version
이 곧 현재 version 입니다 - 새 Version 은 항상 이전보다 큰 번호로만 생깁니다.
"""

from __future__ import annotations

from collections.abc import Callable
from uuid import UUID

import psycopg
from aether_runtime.domain.run import RunStatus

from aether_workflow.application.ports.outbound.agent_run_reader import AgentVersionRef


class PostgresAgentRunReader:
    def __init__(self, connect: Callable[[], psycopg.Connection]) -> None:
        self._connect = connect

    def status(self, agent_run_id: UUID) -> RunStatus | None:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT status::text FROM data.run_executions WHERE run_id = %s",
                (agent_run_id,),
            )
            row = cur.fetchone()
        return None if row is None else RunStatus(row[0])

    def version_for(self, agent_id: UUID, version: int | None) -> AgentVersionRef | None:
        with self._connect() as conn, conn.cursor() as cur:
            if version is None:
                cur.execute(
                    """
                    SELECT id, version FROM control.agent_versions
                    WHERE agent_id = %s ORDER BY version DESC LIMIT 1
                    """,
                    (agent_id,),
                )
            else:
                cur.execute(
                    "SELECT id, version FROM control.agent_versions"
                    " WHERE agent_id = %s AND version = %s",
                    (agent_id, version),
                )
            row = cur.fetchone()
        if row is None:
            return None
        return AgentVersionRef(agent_version_id=row[0], version=row[1])
