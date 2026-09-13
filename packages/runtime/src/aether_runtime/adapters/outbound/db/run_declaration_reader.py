"""spec 0002 2.1, 2.4, D-11: `PostgresRunDeclarationReader` — `RunDeclarationReader`
포트의 PostgreSQL 구현. `control.runs`·`control.agent_versions.definition` 읽기.
`aether_data` 의 SELECT 권한(마이그레이션 0001)이 그 실체입니다 — 이 어댑터는 새
권한을 요구하지 않습니다.

`connect` 는 연결 팩토리입니다(`PostgresRunStateStore` 와 같은 패턴, spec 0001 H-3) —
메서드마다 새 연결을 열고 `with connect() as conn:` 이 커밋·닫기를 맡깁니다. 이
어댑터는 SELECT 만 하므로 커밋할 것이 없지만, 연결을 깨끗이 닫기 위해 같은 패턴을
씁니다.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any
from uuid import UUID

import psycopg

from aether_runtime.application.ports.outbound.run_declaration_reader import RunDeclaration


class PostgresRunDeclarationReader:
    """`control.runs`·`control.agent_versions.definition` 에 대한 PostgreSQL 구현."""

    def __init__(self, connect: Callable[[], psycopg.Connection]) -> None:
        self._connect = connect

    def declaration(self, run_id: UUID) -> RunDeclaration | None:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, agent_version_id, input, cancel_requested_at
                FROM control.runs
                WHERE id = %s
                """,
                (run_id,),
            )
            row = cur.fetchone()
        if row is None:
            return None
        return RunDeclaration(
            run_id=row[0],
            agent_version_id=row[1],
            input=row[2],
            cancel_requested_at=row[3],
        )

    def definition(self, agent_version_id: UUID) -> dict[str, Any]:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT definition FROM control.agent_versions WHERE id = %s",
                (agent_version_id,),
            )
            row = cur.fetchone()
        if row is None:
            raise KeyError(agent_version_id)
        definition: dict[str, Any] = row[0]
        return definition
