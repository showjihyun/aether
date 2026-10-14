"""Workflow 통합 테스트 공용: `control` 에 Workflow 정의와 Run 선언을 관리자 권한으로 심는다.

api 의 `POST /workflows`·`POST /workflows/{id}/runs` 가 하는 일의 최소판입니다 - 실행기
테스트는 api 를 거치지 않고 worker 가 읽는 모양(`control.workflow_runs` + `workflow_versions`)
만 필요합니다.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Callable
from uuid import UUID

import psycopg
from aether_workflow.domain.node import Edge, Node


def declare_workflow_run(
    admin_connection_factory: Callable[[], psycopg.Connection],
    nodes: tuple[Node, ...],
    edges: tuple[Edge, ...],
    *,
    input: dict[str, object] | None = None,
    requested_by: UUID | None = None,
) -> tuple[UUID, UUID]:
    """`(workflow_run_id, workflow_version_id)` 를 돌려줍니다. `requested_by` 는
    `control.api_keys.id`(FK) 여야 합니다 - 비워 두면 0007 이전 행처럼 요청자가 없는 Run 입니다."""
    conn = admin_connection_factory()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO control.workflows (name) VALUES (%s) RETURNING id",
                (f"workflow-{uuid.uuid4()}",),
            )
            row = cur.fetchone()
            assert row is not None
            workflow_id = row[0]
            cur.execute(
                """
                INSERT INTO control.workflow_versions (workflow_id, version, nodes, edges)
                VALUES (%s, 1, %s, %s) RETURNING id
                """,
                (
                    workflow_id,
                    json.dumps(
                        [
                            {
                                "id": n.id,
                                "kind": n.kind.value,
                                "max_iterations": n.max_iterations,
                                "agent_id": str(n.agent_id) if n.agent_id is not None else None,
                                "agent_version": n.agent_version,
                            }
                            for n in nodes
                        ]
                    ),
                    json.dumps(
                        [{"source": e.source, "target": e.target, "label": e.label} for e in edges]
                    ),
                ),
            )
            row = cur.fetchone()
            assert row is not None
            version_id: UUID = row[0]
            cur.execute(
                """
                INSERT INTO control.workflow_runs (workflow_version_id, input, requested_by)
                VALUES (%s, %s, %s) RETURNING id
                """,
                (version_id, json.dumps(input) if input is not None else None, requested_by),
            )
            row = cur.fetchone()
            assert row is not None
            run_id: UUID = row[0]
        conn.commit()
    finally:
        conn.close()
    return run_id, version_id


def issue_api_key(admin_connection_factory: Callable[[], psycopg.Connection]) -> UUID:
    """`control.api_keys` 에 행 하나 - `requested_by` FK 를 만족시키는 주체. 해시는 임의 값이다."""
    conn = admin_connection_factory()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO control.api_keys (label, key_hash) VALUES (%s, %s) RETURNING id",
                (f"test-{uuid.uuid4()}", f"hash-{uuid.uuid4()}"),
            )
            row = cur.fetchone()
            assert row is not None
            key_id: UUID = row[0]
        conn.commit()
    finally:
        conn.close()
    return key_id
