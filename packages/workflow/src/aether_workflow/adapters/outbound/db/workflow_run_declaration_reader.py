"""spec 0005 2.3, 2.9 개정 2: `PostgresWorkflowRunDeclarationReader` -
`WorkflowRunDeclarationReader` 포트의 PostgreSQL 구현. `control.workflow_runs` +
`control.workflow_versions` 읽기. `aether_data` 의 SELECT 권한(마이그레이션 0005)이 그 실체이며
이 어댑터는 새 권한을 요구하지 않습니다 - 읽기만 합니다.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any
from uuid import UUID

import psycopg

from aether_workflow.application.ports.outbound.workflow_run_declaration_reader import (
    WorkflowRunDeclaration,
)
from aether_workflow.domain.node import Edge, Node, NodeKind


def _node(raw: dict[str, Any]) -> Node:
    """`agent_id`·`agent_version` 키는 B1 이 더했습니다 - 그 전에 저장된 Version 에는 **없으므로**
    `.get` 입니다(`KeyError` 로 터지면 옛 Run 이 전부 죽습니다)."""
    agent_id = raw.get("agent_id")
    return Node(
        id=raw["id"],
        kind=NodeKind(raw["kind"]),
        max_iterations=raw.get("max_iterations"),
        agent_id=UUID(agent_id) if agent_id is not None else None,
        agent_version=raw.get("agent_version"),
    )


class PostgresWorkflowRunDeclarationReader:
    def __init__(self, connect: Callable[[], psycopg.Connection]) -> None:
        self._connect = connect

    def declaration(self, workflow_run_id: UUID) -> WorkflowRunDeclaration | None:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT r.id, r.workflow_version_id, v.version, v.nodes, v.edges, r.input,
                       r.cancel_requested_at, r.requested_by
                FROM control.workflow_runs r
                JOIN control.workflow_versions v ON v.id = r.workflow_version_id
                WHERE r.id = %s
                """,
                (workflow_run_id,),
            )
            row = cur.fetchone()
        if row is None:
            return None
        return WorkflowRunDeclaration(
            workflow_run_id=row[0],
            workflow_version_id=row[1],
            version_number=row[2],
            nodes=tuple(_node(n) for n in row[3]),
            edges=tuple(
                Edge(source=e["source"], target=e["target"], label=e.get("label")) for e in row[4]
            ),
            input=row[5],
            cancel_requested_at=row[6],
            requested_by=row[7],
        )
