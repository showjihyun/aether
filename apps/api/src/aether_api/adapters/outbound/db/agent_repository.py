"""spec 0002 2.1, 2.2, 2.10, D-9: `AgentRepository` 의 PostgreSQL 구현.

`connect` 는 연결 **팩토리**입니다(`PostgresApiKeyStore`·`PostgresRunStateStore` 와 같은
패턴) — 메서드마다 새 연결을 열고 `with connect() as conn:` 블록이 커밋(성공 시)·
롤백(예외 시)·닫기를 전부 맡깁니다(psycopg3 의 `Connection.__exit__`).

`add_version` 은 **한 트랜잭션**에서 `agents` 행을 `SELECT … FOR UPDATE` 로 잠근 뒤
`current_version + 1` 로 `agent_versions` 를 INSERT 하고 `agents.current_version`·
`updated_at` 을 갱신합니다 — 동시 요청은 잠금으로 직렬화되고, 그래도 unique 위반이
나면(잠금 밖 경로) `AgentVersionConflict` 로 바꿔 던집니다.

`definition` 은 `jsonb` 로 `model_dump_json()` 저장·`model_validate` 복원합니다 —
psycopg3 는 `jsonb` 열을 이미 파싱된 Python 객체(dict)로 돌려주므로(`RunState`
저장소와 같은 방식) `json.loads` 를 다시 하지 않습니다.

커서는 `(created_at, id)` 를 `|` 로 이어 base64url 로 감싼 불투명 문자열입니다.
"""

from __future__ import annotations

import base64
import builtins
from collections.abc import Callable
from datetime import datetime
from uuid import UUID

import psycopg
from aether_runtime.domain.agent import AgentDefinition

from aether_api.domain.agent import (
    Agent,
    AgentDetail,
    AgentNameTaken,
    AgentNotFound,
    AgentPage,
    AgentVersion,
    AgentVersionConflict,
    AgentVersionNotFound,
    AgentVersionSummary,
)

_AgentRow = tuple[UUID, str, int, datetime, datetime]
_AgentVersionRow = tuple[UUID, UUID, int, dict[str, object], datetime]


def _row_to_agent(row: _AgentRow) -> Agent:
    agent_id, name, current_version, created_at, updated_at = row
    return Agent(
        id=agent_id,
        name=name,
        current_version=current_version,
        created_at=created_at,
        updated_at=updated_at,
    )


def _row_to_agent_version(row: _AgentVersionRow) -> AgentVersion:
    version_id, agent_id, version, definition_raw, created_at = row
    return AgentVersion(
        id=version_id,
        agent_id=agent_id,
        version=version,
        definition=AgentDefinition.model_validate(definition_raw),
        created_at=created_at,
    )


def _encode_cursor(created_at: datetime, agent_id: UUID) -> str:
    raw = f"{created_at.isoformat()}|{agent_id}"
    return base64.urlsafe_b64encode(raw.encode("utf-8")).decode("ascii")


def _decode_cursor(cursor: str) -> tuple[datetime, UUID]:
    raw = base64.urlsafe_b64decode(cursor.encode("ascii")).decode("utf-8")
    created_at_str, id_str = raw.split("|", 1)
    return datetime.fromisoformat(created_at_str), UUID(id_str)


class PostgresAgentRepository:
    """`control.agents`·`control.agent_versions` 에 대한 outbound 포트 구현."""

    def __init__(self, connect: Callable[[], psycopg.Connection]) -> None:
        self._connect = connect

    def create(self, name: str, definition: AgentDefinition) -> Agent:
        with self._connect() as conn, conn.cursor() as cur:
            try:
                cur.execute(
                    """
                    INSERT INTO control.agents (name)
                    VALUES (%s)
                    RETURNING id, name, current_version, created_at, updated_at
                    """,
                    (name,),
                )
            except psycopg.errors.UniqueViolation as exc:
                raise AgentNameTaken(name) from exc
            row = cur.fetchone()
            if row is None:  # pragma: no cover - INSERT ... RETURNING always yields a row
                raise RuntimeError("INSERT ... RETURNING control.agents returned no row")
            agent = _row_to_agent(row)
            cur.execute(
                """
                INSERT INTO control.agent_versions (agent_id, version, definition)
                VALUES (%s, 1, %s)
                """,
                (agent.id, definition.model_dump_json()),
            )
        return agent

    def get(self, agent_id: UUID) -> Agent:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT id, name, current_version, created_at, updated_at "
                "FROM control.agents WHERE id = %s",
                (agent_id,),
            )
            row = cur.fetchone()
        if row is None:
            raise AgentNotFound(agent_id)
        return _row_to_agent(row)

    def list(self, limit: int, cursor: str | None) -> AgentPage:
        with self._connect() as conn, conn.cursor() as cur:
            if cursor is None:
                cur.execute(
                    """
                    SELECT id, name, current_version, created_at, updated_at
                    FROM control.agents
                    ORDER BY created_at, id
                    LIMIT %s
                    """,
                    (limit + 1,),
                )
            else:
                after_created_at, after_id = _decode_cursor(cursor)
                cur.execute(
                    """
                    SELECT id, name, current_version, created_at, updated_at
                    FROM control.agents
                    WHERE (created_at, id) > (%s, %s)
                    ORDER BY created_at, id
                    LIMIT %s
                    """,
                    (after_created_at, after_id, limit + 1),
                )
            rows = cur.fetchall()

        has_more = len(rows) > limit
        page_rows = rows[:limit]
        items = [_row_to_agent(row) for row in page_rows]
        next_cursor = _encode_cursor(items[-1].created_at, items[-1].id) if has_more else None
        return AgentPage(items=items, next_cursor=next_cursor)

    def get_version(self, agent_id: UUID, version: int) -> AgentVersion:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute("SELECT 1 FROM control.agents WHERE id = %s", (agent_id,))
            if cur.fetchone() is None:
                raise AgentNotFound(agent_id)
            cur.execute(
                """
                SELECT id, agent_id, version, definition, created_at
                FROM control.agent_versions
                WHERE agent_id = %s AND version = %s
                """,
                (agent_id, version),
            )
            row = cur.fetchone()
        if row is None:
            raise AgentVersionNotFound((agent_id, version))
        return _row_to_agent_version(row)

    def list_versions(self, agent_id: UUID) -> builtins.list[AgentVersionSummary]:
        """`builtins.list` — 이 클래스의 `list` 메서드가 클래스 본문에서 내장 `list` 를 가립니다."""
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute("SELECT 1 FROM control.agents WHERE id = %s", (agent_id,))
            if cur.fetchone() is None:
                raise AgentNotFound(agent_id)
            cur.execute(
                """
                SELECT version, created_at FROM control.agent_versions
                WHERE agent_id = %s
                ORDER BY version
                """,
                (agent_id,),
            )
            rows = cur.fetchall()
        return [AgentVersionSummary(version=row[0], created_at=row[1]) for row in rows]

    def add_version(self, agent_id: UUID, definition: AgentDefinition) -> AgentDetail:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, name, current_version, created_at, updated_at
                FROM control.agents
                WHERE id = %s
                FOR UPDATE
                """,
                (agent_id,),
            )
            row = cur.fetchone()
            if row is None:
                raise AgentNotFound(agent_id)
            agent = _row_to_agent(row)
            new_version_number = agent.current_version + 1

            try:
                cur.execute(
                    """
                    INSERT INTO control.agent_versions (agent_id, version, definition)
                    VALUES (%s, %s, %s)
                    """,
                    (agent_id, new_version_number, definition.model_dump_json()),
                )
            except psycopg.errors.UniqueViolation as exc:
                raise AgentVersionConflict(agent_id) from exc

            cur.execute(
                """
                UPDATE control.agents
                SET current_version = %s, updated_at = now()
                WHERE id = %s
                RETURNING id, name, current_version, created_at, updated_at
                """,
                (new_version_number, agent_id),
            )
            updated_row = cur.fetchone()
            if updated_row is None:  # pragma: no cover - row was just locked above
                raise RuntimeError("UPDATE ... RETURNING control.agents returned no row")

            cur.execute(
                """
                SELECT version, created_at FROM control.agent_versions
                WHERE agent_id = %s
                ORDER BY version
                """,
                (agent_id,),
            )
            version_rows = cur.fetchall()

        updated_agent = _row_to_agent(updated_row)
        versions = [AgentVersionSummary(version=row[0], created_at=row[1]) for row in version_rows]
        return AgentDetail(agent=updated_agent, definition=definition, versions=versions)
