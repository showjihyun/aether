"""🔒 spec 0003 2.14, D-14, 개정 4, P2-4: `SetToolPermissionUseCase`.

`GetAgentVersion`(기존 포트, `FakeAgentRepository`) 으로 `(agent_id, version)` 을
해석하고, `ToolPermissionStore`(fake)에 `agent_version_id` 로 upsert 합니다. Agent 나
버전이 없으면 `agents_get_version` 과 같은 예외가 그대로 전파됩니다.

`test_upserts_into_a_single_row`·`test_visible_to_postgres_permission_table` 은
실제 PostgreSQL 로 `PostgresToolPermissionStore`(쓰기, `aether_control`) →
`aether_policy.PostgresPermissionTable`(읽기, `aether_data`)를 잇습니다(spec R-4 판정
목록의 4·9번).
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Callable
from typing import Any
from uuid import UUID

import psycopg
import pytest
from aether_api.application.usecases.create_agent import CreateAgentUseCase
from aether_api.application.usecases.get_agent_version import GetAgentVersionUseCase
from aether_api.application.usecases.set_tool_permission import SetToolPermissionUseCase
from aether_api.domain.agent import AgentNotFound, AgentVersionNotFound
from aether_policy.domain.decision import Decision
from aether_runtime.domain.agent import AgentDefinition

from apps.api.tests.fakes import FakeAgentRepository


def _definition(**overrides: Any) -> AgentDefinition:
    payload: dict[str, Any] = {"schema_version": 1, "system_prompt": "You are a helper."}
    payload.update(overrides)
    return AgentDefinition.model_validate(payload)


class FakeToolPermissionStore:
    """`ToolPermissionStore` outbound 포트의 dict 기반 fake — 같은 키는 덮어씁니다."""

    def __init__(self) -> None:
        self.rows: dict[tuple[UUID, str, str], Decision] = {}
        self.calls: list[tuple[UUID, str, str, Decision]] = []

    def upsert(
        self, agent_version_id: UUID, server_name: str, tool_name: str, decision: Decision
    ) -> None:
        self.calls.append((agent_version_id, server_name, tool_name, decision))
        self.rows[(agent_version_id, server_name, tool_name)] = decision


def test_resolves_agent_version_id_and_upserts_into_the_store() -> None:
    repo = FakeAgentRepository()
    create_agent = CreateAgentUseCase(repo)
    agent = create_agent("weather-bot", _definition())
    get_agent_version = GetAgentVersionUseCase(repo)
    agent_version = get_agent_version(agent.id, 1)
    store = FakeToolPermissionStore()
    set_tool_permission = SetToolPermissionUseCase(get_agent_version, store)

    set_tool_permission(agent.id, 1, "filesystem", "read", "allow")

    assert store.calls == [(agent_version.id, "filesystem", "read", "allow")]


def test_missing_agent_raises_agent_not_found() -> None:
    repo = FakeAgentRepository()
    store = FakeToolPermissionStore()
    set_tool_permission = SetToolPermissionUseCase(GetAgentVersionUseCase(repo), store)

    with pytest.raises(AgentNotFound):
        set_tool_permission(uuid.uuid4(), 1, "filesystem", "read", "allow")
    assert store.calls == []


def test_missing_version_raises_agent_version_not_found() -> None:
    repo = FakeAgentRepository()
    create_agent = CreateAgentUseCase(repo)
    agent = create_agent("weather-bot", _definition())
    store = FakeToolPermissionStore()
    set_tool_permission = SetToolPermissionUseCase(GetAgentVersionUseCase(repo), store)

    with pytest.raises(AgentVersionNotFound):
        set_tool_permission(agent.id, 2, "filesystem", "read", "allow")
    assert store.calls == []


def _insert_agent_version(
    admin_conn: psycopg.Connection, name: str
) -> tuple[uuid.UUID, uuid.UUID, int]:
    """실제 API 등록 경로가 아니라 admin 역할로 최소 행만 만듭니다(마이그레이션 전제)."""
    with admin_conn.cursor() as cur:
        cur.execute("INSERT INTO control.agents (name) VALUES (%s) RETURNING id", (name,))
        row = cur.fetchone()
        assert row is not None
        agent_id: uuid.UUID = row[0]

        cur.execute(
            """
            INSERT INTO control.agent_versions (agent_id, version, definition)
            VALUES (%s, 1, %s)
            RETURNING id
            """,
            (agent_id, json.dumps({"schema_version": 1, "system_prompt": "You are a helper."})),
        )
        row = cur.fetchone()
        assert row is not None
        version_row_id: uuid.UUID = row[0]
    admin_conn.commit()
    return agent_id, version_row_id, 1


@pytest.mark.integration
def test_upserts_into_a_single_row(
    admin_connection_factory: Callable[[], psycopg.Connection],
    control_connection_factory: Callable[[], psycopg.Connection],
) -> None:
    """spec 개정 4, D-14: 같은 키에 다시 적용하면 행이 1개로 덮어써집니다(upsert)."""
    from aether_api.adapters.outbound.db.agent_repository import PostgresAgentRepository
    from aether_api.adapters.outbound.db.tool_permissions import PostgresToolPermissionStore

    admin_conn = admin_connection_factory()
    try:
        agent_id, version_id, version = _insert_agent_version(admin_conn, f"agent-{uuid.uuid4()}")
    finally:
        admin_conn.close()

    repository = PostgresAgentRepository(control_connection_factory)
    store = PostgresToolPermissionStore(control_connection_factory)
    set_tool_permission = SetToolPermissionUseCase(GetAgentVersionUseCase(repository), store)

    set_tool_permission(agent_id, version, "filesystem", "read", "allow")
    set_tool_permission(agent_id, version, "filesystem", "read", "deny")

    conn = admin_connection_factory()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT decision FROM control.tool_permissions "
                "WHERE agent_version_id = %s AND server_name = %s AND tool_name = %s",
                (version_id, "filesystem", "read"),
            )
            rows = cur.fetchall()
    finally:
        conn.close()

    assert len(rows) == 1
    assert rows[0][0] == "deny"


@pytest.mark.integration
def test_declared_permission_is_visible_to_postgres_permission_table(
    admin_connection_factory: Callable[[], psycopg.Connection],
    control_connection_factory: Callable[[], psycopg.Connection],
    data_connection_factory: Callable[[], psycopg.Connection],
) -> None:
    """spec R-4·D-14 판정 9번: CLI 경로로 넣은 행이 `PostgresPermissionTable` 의 판정에 반영됨."""
    from aether_api.adapters.outbound.db.agent_repository import PostgresAgentRepository
    from aether_api.adapters.outbound.db.tool_permissions import PostgresToolPermissionStore
    from aether_policy.adapters.outbound.permission_table.postgres import PostgresPermissionTable
    from aether_policy.application.usecases.judge_tool_call import JudgeToolCallUseCase

    admin_conn = admin_connection_factory()
    try:
        agent_id, version_id, version = _insert_agent_version(admin_conn, f"agent-{uuid.uuid4()}")
    finally:
        admin_conn.close()

    repository = PostgresAgentRepository(control_connection_factory)
    store = PostgresToolPermissionStore(control_connection_factory)
    set_tool_permission = SetToolPermissionUseCase(GetAgentVersionUseCase(repository), store)

    set_tool_permission(agent_id, version, "filesystem", "read", "allow")

    judge = JudgeToolCallUseCase(PostgresPermissionTable(data_connection_factory))
    assert judge(version_id, "filesystem", "read") == "allow"
    assert judge(version_id, "filesystem", "write") == "deny"
