"""spec 0005 2.9, D-12: `WorkflowRepository` 의 PostgreSQL 구현.

`connect` 는 연결 **팩토리**입니다(`PostgresAgentRepository` 와 같은 패턴) — 메서드마다 새
연결을 열고 `with connect() as conn:` 이 커밋·롤백·닫기를 맡습니다. `aether_control` 역할로
접속합니다(마이그레이션 0005 GRANT).

`add_version` 은 **한 트랜잭션**에서 `workflows` 행을 `SELECT … FOR UPDATE` 로 잠근 뒤
`current_version + 1` 로 `workflow_versions` 를 INSERT 하고 `current_version` 을 갱신합니다.
기존 Version 행은 읽지도 바꾸지도 않습니다 — DB 트리거도 UPDATE·DELETE 를 거부합니다(D-12).

`nodes`·`edges` 는 `jsonb` 로 저장하고 `aether_workflow.domain` 의 값 객체로 복원합니다.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any
from uuid import UUID

import psycopg
from aether_workflow.domain.condition import ConditionOperator
from aether_workflow.domain.node import Edge, Node, NodeKind
from aether_workflow.domain.workflow_version import WorkflowVersion

from aether_api.adapters.outbound.db.cursor import decode_cursor, encode_cursor
from aether_api.domain.workflow import (
    WorkflowNotFound,
    WorkflowPage,
    WorkflowSummary,
    WorkflowView,
)


def _nodes_to_json(nodes: tuple[Node, ...]) -> str:
    return json.dumps(
        [
            {
                "id": n.id,
                "kind": n.kind.value,
                "max_iterations": n.max_iterations,
                "agent_id": str(n.agent_id) if n.agent_id is not None else None,
                "agent_version": n.agent_version,
                "condition_path": n.condition_path,
                "condition_operator": (
                    n.condition_operator.value if n.condition_operator is not None else None
                ),
                "condition_value": n.condition_value,
                "wait_seconds": n.wait_seconds,
                "llm_prompt": n.llm_prompt,
                "llm_prompt_path": n.llm_prompt_path,
                "tool_server": n.tool_server,
                "tool_name": n.tool_name,
                "tool_arguments": n.tool_arguments,
                "tool_arguments_path": n.tool_arguments_path,
            }
            for n in nodes
        ]
    )


def _node_from_json(n: dict[str, Any]) -> Node:
    """`agent_id`·`agent_version` 은 P4-2a B1 이, `condition_*` 세 키는 P4-2b 가, `wait_seconds` 는
    P4-3 이, `llm_*`·`tool_*` 여섯 키는 P4-5 가 더한 키입니다 —
    그 전에 저장된 Version 의 행에는 **없으므로** `.get` 으로 읽고 없으면 `None` 입니다(`KeyError`
    로 터지지 않게)."""
    raw_agent_id = n.get("agent_id")
    operator = n.get("condition_operator")
    return Node(
        id=n["id"],
        kind=NodeKind(n["kind"]),
        max_iterations=n["max_iterations"],
        agent_id=UUID(raw_agent_id) if raw_agent_id is not None else None,
        agent_version=n.get("agent_version"),
        condition_path=n.get("condition_path"),
        condition_operator=ConditionOperator(operator) if operator is not None else None,
        condition_value=n.get("condition_value"),
        wait_seconds=n.get("wait_seconds"),
        llm_prompt=n.get("llm_prompt"),
        llm_prompt_path=n.get("llm_prompt_path"),
        tool_server=n.get("tool_server"),
        tool_name=n.get("tool_name"),
        tool_arguments=n.get("tool_arguments"),
        tool_arguments_path=n.get("tool_arguments_path"),
    )


def _edges_to_json(edges: tuple[Edge, ...]) -> str:
    return json.dumps([{"source": e.source, "target": e.target, "label": e.label} for e in edges])


def _version_from_row(
    number: int, nodes_raw: list[dict[str, Any]], edges_raw: list[dict[str, Any]]
) -> WorkflowVersion:
    return WorkflowVersion(
        number=number,
        nodes=tuple(_node_from_json(n) for n in nodes_raw),
        edges=tuple(
            Edge(source=e["source"], target=e["target"], label=e["label"]) for e in edges_raw
        ),
    )


class PostgresWorkflowRepository:
    """`control.workflows`·`control.workflow_versions` 에 대한 outbound 포트 구현."""

    def __init__(self, connect: Callable[[], psycopg.Connection]) -> None:
        self._connect = connect

    def create(self, name: str, nodes: tuple[Node, ...], edges: tuple[Edge, ...]) -> WorkflowView:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute("INSERT INTO control.workflows (name) VALUES (%s) RETURNING id", (name,))
            row = cur.fetchone()
            if row is None:  # pragma: no cover - INSERT ... RETURNING always yields a row
                raise RuntimeError("INSERT ... RETURNING control.workflows returned no row")
            workflow_id: UUID = row[0]
            cur.execute(
                """
                INSERT INTO control.workflow_versions (workflow_id, version, nodes, edges)
                VALUES (%s, 1, %s, %s)
                """,
                (workflow_id, _nodes_to_json(nodes), _edges_to_json(edges)),
            )
        return WorkflowView(
            id=workflow_id,
            name=name,
            latest_version=WorkflowVersion(number=1, nodes=nodes, edges=edges),
        )

    def add_version(
        self, workflow_id: UUID, nodes: tuple[Node, ...], edges: tuple[Edge, ...]
    ) -> WorkflowView:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT name, current_version FROM control.workflows WHERE id = %s FOR UPDATE",
                (workflow_id,),
            )
            row = cur.fetchone()
            if row is None:
                raise WorkflowNotFound(workflow_id)
            name, current_version = row
            new_number = current_version + 1
            cur.execute(
                """
                INSERT INTO control.workflow_versions (workflow_id, version, nodes, edges)
                VALUES (%s, %s, %s, %s)
                """,
                (workflow_id, new_number, _nodes_to_json(nodes), _edges_to_json(edges)),
            )
            cur.execute(
                "UPDATE control.workflows SET current_version = %s, updated_at = now() "
                "WHERE id = %s",
                (new_number, workflow_id),
            )
        return WorkflowView(
            id=workflow_id,
            name=name,
            latest_version=WorkflowVersion(number=new_number, nodes=nodes, edges=edges),
        )

    def get(self, workflow_id: UUID) -> WorkflowView | None:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT w.name, v.version, v.nodes, v.edges
                FROM control.workflows w
                JOIN control.workflow_versions v
                  ON v.workflow_id = w.id AND v.version = w.current_version
                WHERE w.id = %s
                """,
                (workflow_id,),
            )
            row = cur.fetchone()
        if row is None:
            return None
        name, number, nodes_raw, edges_raw = row
        return WorkflowView(
            id=workflow_id,
            name=name,
            latest_version=_version_from_row(number, nodes_raw, edges_raw),
        )

    def get_version(self, workflow_id: UUID, number: int) -> WorkflowVersion | None:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT version, nodes, edges FROM control.workflow_versions "
                "WHERE workflow_id = %s AND version = %s",
                (workflow_id, number),
            )
            row = cur.fetchone()
        if row is None:
            return None
        return _version_from_row(*row)

    def list(self, limit: int, cursor: str | None) -> WorkflowPage:
        """`(created_at, id)` 오름차순 커서 페이지(spec 0006 D-3). 노드·간선은 읽지 않습니다."""
        conditions = ""
        params: dict[str, object] = {"limit": limit + 1}
        if cursor is not None:
            after_at, after_id = decode_cursor(cursor)
            conditions = "WHERE (created_at, id) > (%(after_at)s, %(after_id)s)"
            params["after_at"] = after_at
            params["after_id"] = after_id
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT id, name, current_version, created_at, updated_at
                FROM control.workflows
                {conditions}
                ORDER BY created_at, id
                LIMIT %(limit)s
                """,
                params,
            )
            rows = cur.fetchall()
        has_more = len(rows) > limit
        items = [
            WorkflowSummary(
                id=row[0],
                name=row[1],
                current_version=row[2],
                created_at=row[3],
                updated_at=row[4],
            )
            for row in rows[:limit]
        ]
        next_cursor = encode_cursor(items[-1].created_at, items[-1].id) if has_more else None
        return WorkflowPage(items=items, next_cursor=next_cursor)
