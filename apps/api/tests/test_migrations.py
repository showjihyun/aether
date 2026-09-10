"""spec R-8: 초기화 스크립트 없는 빈 DB(testcontainers)에서 마이그레이션 왕복.

역할은 `db_roles`(conftest) 가 이미 만들어 둔 상태 위에서, `upgrade head` →
`downgrade base` → `upgrade head` 가 예외 없이 끝나고 `control`·`data` 스키마와
다섯 테이블이 실재하는지만 봅니다. 열·제약의 세부는 다른 테스트 파일이 봅니다.
"""

from __future__ import annotations

from collections.abc import Callable

import psycopg
import pytest
from alembic import command
from alembic.config import Config

pytestmark = pytest.mark.integration

_EXPECTED_TABLES = {
    ("control", "agents"),
    ("control", "agent_versions"),
    ("control", "api_keys"),
    ("control", "runs"),
    ("data", "run_executions"),
}


def test_upgrade_downgrade_upgrade_round_trip_recreates_expected_tables(
    alembic_config: Config,
    admin_connection_factory: Callable[[], psycopg.Connection],
) -> None:
    command.upgrade(alembic_config, "head")
    command.downgrade(alembic_config, "base")
    command.upgrade(alembic_config, "head")

    conn = admin_connection_factory()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT table_schema, table_name
                FROM information_schema.tables
                WHERE table_schema IN ('control', 'data')
                """
            )
            found = {(schema, name) for schema, name in cur.fetchall()}
    finally:
        conn.close()

    assert _EXPECTED_TABLES <= found
