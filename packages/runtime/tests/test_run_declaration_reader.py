"""spec 0002 2.1, 2.4, D-11 (P1-5a): `PostgresRunDeclarationReader` — `control.runs`·
`control.agent_versions.definition` 읽기. `aether_data` 의 SELECT 권한이 그 실체입니다
(이미 마이그레이션 0001 이 부여했습니다 — 이 단위는 코드만 더합니다).

관리자 접속으로 `control.agents` → `agent_versions` → `runs` 를 심고, `aether_data`
역할(`data_connection_factory`)로 읽습니다 — `test_run_state_store_contract.py` 의
`_declare_run` 과 같은 절차입니다.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from uuid import UUID

import psycopg
import pytest
from aether_runtime.adapters.outbound.db.run_declaration_reader import (
    PostgresRunDeclarationReader,
)

pytestmark = pytest.mark.integration


def _declare_run(
    admin_connection_factory: Callable[[], psycopg.Connection],
    *,
    definition: dict[str, object] | None = None,
    run_input: str = "reader-test-input",
) -> tuple[UUID, UUID]:
    """`control.agents` → `agent_versions` → `runs` 를 관리자 권한으로 심고
    `(run_id, agent_version_id)` 를 돌려줍니다."""
    if definition is None:
        definition = {"schema_version": 1}
    conn = admin_connection_factory()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO control.agents (name) VALUES (%s) RETURNING id",
                (f"agent-{uuid.uuid4()}",),
            )
            row = cur.fetchone()
            assert row is not None
            agent_id = row[0]

            cur.execute(
                """
                INSERT INTO control.agent_versions (agent_id, version, definition)
                VALUES (%s, %s, %s)
                RETURNING id
                """,
                (agent_id, 1, json.dumps(definition)),
            )
            row = cur.fetchone()
            assert row is not None
            agent_version_id: UUID = row[0]

            cur.execute(
                """
                INSERT INTO control.runs (agent_version_id, input)
                VALUES (%s, %s)
                RETURNING id
                """,
                (agent_version_id, run_input),
            )
            row = cur.fetchone()
            assert row is not None
            run_id: UUID = row[0]
        conn.commit()
    finally:
        conn.close()
    return run_id, agent_version_id


def test_declaration_returns_run_fields(
    admin_connection_factory: Callable[[], psycopg.Connection],
    data_connection_factory: Callable[[], psycopg.Connection],
) -> None:
    run_id, agent_version_id = _declare_run(admin_connection_factory, run_input="hello world")
    reader = PostgresRunDeclarationReader(data_connection_factory)

    declaration = reader.declaration(run_id)

    assert declaration is not None
    assert declaration.run_id == run_id
    assert declaration.agent_version_id == agent_version_id
    assert declaration.input == "hello world"
    assert declaration.cancel_requested_at is None


def test_declaration_returns_none_for_unknown_run(
    data_connection_factory: Callable[[], psycopg.Connection],
) -> None:
    reader = PostgresRunDeclarationReader(data_connection_factory)

    assert reader.declaration(uuid.uuid4()) is None


def test_definition_returns_the_stored_agent_version_definition(
    admin_connection_factory: Callable[[], psycopg.Connection],
    data_connection_factory: Callable[[], psycopg.Connection],
) -> None:
    definition = {"schema_version": 1, "system_prompt": "You are helpful."}
    _run_id, agent_version_id = _declare_run(admin_connection_factory, definition=definition)
    reader = PostgresRunDeclarationReader(data_connection_factory)

    loaded = reader.definition(agent_version_id)

    assert loaded == definition


def test_definition_raises_key_error_for_unknown_agent_version(
    data_connection_factory: Callable[[], psycopg.Connection],
) -> None:
    reader = PostgresRunDeclarationReader(data_connection_factory)

    with pytest.raises(KeyError):
        reader.definition(uuid.uuid4())


def test_cancel_requested_at_is_reflected_after_admin_sets_it(
    admin_connection_factory: Callable[[], psycopg.Connection],
    data_connection_factory: Callable[[], psycopg.Connection],
) -> None:
    run_id, _agent_version_id = _declare_run(admin_connection_factory)
    reader = PostgresRunDeclarationReader(data_connection_factory)
    initial = reader.declaration(run_id)
    assert initial is not None
    assert initial.cancel_requested_at is None

    now = datetime(2026, 1, 1, tzinfo=UTC)
    conn = admin_connection_factory()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE control.runs SET cancel_requested_at = %s WHERE id = %s",
                (now, run_id),
            )
        conn.commit()
    finally:
        conn.close()

    declaration = reader.declaration(run_id)
    assert declaration is not None
    assert declaration.cancel_requested_at == now
