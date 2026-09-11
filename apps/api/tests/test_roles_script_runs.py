"""`01-roles.sh` 를 실제로 실행해 두 역할이 만들어지는지 검증합니다.

spec 0001 2.8 · R-7 · LP-2 — P0-8 의 단위 테스트(`test_roles_script.py`)는 스크립트
내용을 grep 만 했고, `conftest.py` 의 `db_roles` fixture 는 psycopg 로 역할을 직접
만들어 스크립트 자체를 실행하지 않았습니다. 그래서 psql 의 `:'var'` 치환이
`DO $do$ ... $do$` dollar-quoting 블록 안에서는 적용되지 않는 버그(P0-5 세션이
격리 재현)를 아무 테스트도 잡지 못했습니다. 이 테스트는 스크립트를
`/docker-entrypoint-initdb.d/01-roles.sh` 로 실제 마운트해 postgres 컨테이너
초기화 과정에서 그대로 실행시켜, (a) 초기화 자체가 실패하거나 (b) 초기화는
성공하지만 역할이 만들어지지 않는 두 실패 모드를 모두 잡습니다.
"""

from __future__ import annotations

import uuid
from pathlib import Path

import psycopg
import pytest
from testcontainers.community.postgres import PostgresContainer

pytestmark = pytest.mark.integration

REPO_ROOT = Path(__file__).resolve().parents[3]
ROLES_SCRIPT = REPO_ROOT / "infra" / "docker" / "postgres" / "init" / "01-roles.sh"

_ADMIN_USER = "aether_admin"
_ADMIN_PASSWORD = "aether_admin_pw"
_ADMIN_DB = "aether"

_CONTROL_PASSWORD = f"control-pw-{uuid.uuid4()}"
_DATA_PASSWORD = f"data-pw-{uuid.uuid4()}"


def test_roles_script_creates_both_roles_when_run_by_postgres_entrypoint() -> None:
    assert ROLES_SCRIPT.is_file(), f"스크립트가 없습니다: {ROLES_SCRIPT}"

    container = PostgresContainer(
        image="postgres:16-alpine",
        username=_ADMIN_USER,
        password=_ADMIN_PASSWORD,
        dbname=_ADMIN_DB,
        driver="psycopg",
    )
    container.with_volume_mapping(
        str(ROLES_SCRIPT.resolve()),
        "/docker-entrypoint-initdb.d/01-roles.sh",
        "ro",
    )
    container.with_env("AETHER_CONTROL_PASSWORD", _CONTROL_PASSWORD)
    container.with_env("AETHER_DATA_PASSWORD", _DATA_PASSWORD)

    # 컨테이너 준비 대기 자체가 타임아웃/예외로 실패하면 그것이 실패 모드 (a) —
    # 초기화 스크립트 오류로 postgres 가 준비 상태에 도달하지 못한 것입니다.
    with container as pg:
        host = pg.get_container_host_ip()
        port = int(pg.get_exposed_port(pg.port))

        with psycopg.connect(
            f"host={host} port={port} user={_ADMIN_USER} "
            f"password={_ADMIN_PASSWORD} dbname={_ADMIN_DB}"
        ) as admin_conn:
            with admin_conn.cursor() as cur:
                cur.execute(
                    "SELECT rolname FROM pg_catalog.pg_roles WHERE rolname IN (%s, %s)",
                    ("aether_control", "aether_data"),
                )
                found = {row[0] for row in cur.fetchall()}

        # 실패 모드 (b): 초기화는 성공했지만 역할이 만들어지지 않음.
        assert found == {"aether_control", "aether_data"}, (
            f"스크립트가 두 역할을 만들지 않았습니다(만들어진 것: {found})"
        )

        # 치환이 실제로 일어났다는 증명 — 발급한 비밀번호로 접속이 됩니다.
        with psycopg.connect(
            f"host={host} port={port} user=aether_control "
            f"password={_CONTROL_PASSWORD} dbname={_ADMIN_DB}"
        ):
            pass
        with psycopg.connect(
            f"host={host} port={port} user=aether_data password={_DATA_PASSWORD} dbname={_ADMIN_DB}"
        ):
            pass
