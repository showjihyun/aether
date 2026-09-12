"""`integration` 마커 통합 테스트 공통 PostgreSQL fixture (spec 0001 2.8, R-7, R-8. spec 0002 2.16).

세션당 PostgreSQL 컨테이너 하나(testcontainers)를 띄우고, 관리자 역할로
`aether_control`·`aether_data` 두 역할을 만든 뒤(`infra/docker/postgres/init/01-roles.sh`
와 같은 문장), 관리자 역할로 `apps/api/migrations` 를 `head` 까지 올립니다. 그 위에서
관리자·`aether_control`·`aether_data` 세 접속 팩토리를 테스트에 건넵니다.

역할은 클러스터 수준이라 마이그레이션이 만들 수 없고, 초기화 스크립트가 만듭니다
(spec 2.8). 이 fixture 모듈은 그 스크립트가 없는 testcontainers 환경에서 같은 일을
Python 으로 합니다.

원래 `apps/api/tests/conftest.py` 에 있던 fixture 전부를 여기로 옮겼습니다(spec 0002
P1-2a) — `apps/api`·`apps/worker`·`packages/runtime` 의 테스트가 같은 컨테이너·역할·
마이그레이션 fixture 를 `pytest_plugins = ["tests.support.pg"]` 한 줄로 공유하기
위해서입니다. fixture 이름은 그대로라 이 모듈을 쓰던 기존 테스트는 바뀌지 않습니다.
"""

from __future__ import annotations

import os
from collections.abc import Callable, Iterator
from pathlib import Path

import psycopg
import pytest
from alembic import command
from alembic.config import Config
from psycopg import sql
from testcontainers.community.postgres import PostgresContainer

REPO_ROOT = Path(__file__).resolve().parents[2]
MIGRATIONS_DIR = REPO_ROOT / "apps" / "api" / "migrations"

_ADMIN_USER = "aether_admin"
_ADMIN_PASSWORD = "aether_admin_pw"
_ADMIN_DB = "aether"

CONTROL_ROLE = "aether_control"
CONTROL_PASSWORD = "aether_control_pw"
DATA_ROLE = "aether_data"
DATA_PASSWORD = "aether_data_pw"


def _dsn(host: str, port: int, user: str, password: str, dbname: str) -> str:
    """psycopg 가 받는 conninfo 문자열. SQLAlchemy 의 `+psycopg` URL 과는 형식이 다릅니다."""
    return f"host={host} port={port} user={user} password={password} dbname={dbname}"


def _sqlalchemy_url(host: str, port: int, user: str, password: str, dbname: str) -> str:
    return f"postgresql+psycopg://{user}:{password}@{host}:{port}/{dbname}"


def _create_role_if_missing(admin_conn: psycopg.Connection, role: str, password: str) -> None:
    """`01-roles.sh` 와 같은 문장 — 이미 있으면 건너뜁니다."""
    with admin_conn.cursor() as cur:
        cur.execute("SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = %s", (role,))
        if cur.fetchone() is not None:
            return
        cur.execute(
            sql.SQL("CREATE ROLE {role} LOGIN PASSWORD {password}").format(
                role=sql.Identifier(role),
                password=sql.Literal(password),
            )
        )


@pytest.fixture(scope="session")
def postgres_container() -> Iterator[PostgresContainer]:
    with PostgresContainer(
        image="postgres:16-alpine",
        username=_ADMIN_USER,
        password=_ADMIN_PASSWORD,
        dbname=_ADMIN_DB,
        driver="psycopg",
    ) as container:
        yield container


@pytest.fixture(scope="session")
def db_host_port(postgres_container: PostgresContainer) -> tuple[str, int]:
    host = postgres_container.get_container_host_ip()
    port = int(postgres_container.get_exposed_port(postgres_container.port))
    return host, port


@pytest.fixture(scope="session")
def admin_database_url(db_host_port: tuple[str, int]) -> str:
    """alembic 이 읽는 SQLAlchemy 형식 URL."""
    host, port = db_host_port
    return _sqlalchemy_url(host, port, _ADMIN_USER, _ADMIN_PASSWORD, _ADMIN_DB)


@pytest.fixture
def control_database_url(migrated_database: None, db_host_port: tuple[str, int]) -> str:
    """`aether_control` 역할의 SQLAlchemy 형식 URL(spec 2.9 H-3).

    `Settings.database_url`/`AETHER_DATABASE_URL` 이 기대하는 형식과 같습니다 —
    `Settings.psycopg_dsn` 이 여기서 `+psycopg` 표기를 벗겨 libpq 형식으로 씁니다.
    CLI 서브프로세스 통합 테스트(`test_keys_cli.py`)와 조립 통합 테스트
    (`test_auth_end_to_end.py`)가 이 URL 을 씁니다 — 마이그레이션 실행 역할(관리자)이
    아니라 api 의 런타임 역할로 접속해야 하기 때문입니다.
    """
    host, port = db_host_port
    return _sqlalchemy_url(host, port, CONTROL_ROLE, CONTROL_PASSWORD, _ADMIN_DB)


@pytest.fixture(scope="session")
def db_roles(db_host_port: tuple[str, int]) -> None:
    """`aether_control`, `aether_data` 역할만 만듭니다. 스키마·테이블은 마이그레이션이 만듭니다."""
    host, port = db_host_port
    with psycopg.connect(
        _dsn(host, port, _ADMIN_USER, _ADMIN_PASSWORD, _ADMIN_DB), autocommit=True
    ) as conn:
        _create_role_if_missing(conn, CONTROL_ROLE, CONTROL_PASSWORD)
        _create_role_if_missing(conn, DATA_ROLE, DATA_PASSWORD)


@pytest.fixture(scope="session")
def alembic_config(db_roles: None, admin_database_url: str) -> Iterator[Config]:
    """관리자 URL 로 `ALEMBIC_URL` 을 설정한 뒤 `Config` 를 건넵니다(env.py 가 그 변수를 읽음)."""
    previous = os.environ.get("ALEMBIC_URL")
    os.environ["ALEMBIC_URL"] = admin_database_url
    try:
        yield Config(str(MIGRATIONS_DIR / "alembic.ini"))
    finally:
        if previous is None:
            os.environ.pop("ALEMBIC_URL", None)
        else:
            os.environ["ALEMBIC_URL"] = previous


@pytest.fixture(scope="session")
def migrated_database(alembic_config: Config) -> None:
    """관리자 역할로 `alembic upgrade head`."""
    command.upgrade(alembic_config, "head")


@pytest.fixture
def admin_connection_factory(
    migrated_database: None, db_host_port: tuple[str, int]
) -> Callable[[], psycopg.Connection]:
    host, port = db_host_port

    def _connect() -> psycopg.Connection:
        return psycopg.connect(_dsn(host, port, _ADMIN_USER, _ADMIN_PASSWORD, _ADMIN_DB))

    return _connect


@pytest.fixture
def control_connection_factory(
    migrated_database: None, db_host_port: tuple[str, int]
) -> Callable[[], psycopg.Connection]:
    host, port = db_host_port

    def _connect() -> psycopg.Connection:
        return psycopg.connect(_dsn(host, port, CONTROL_ROLE, CONTROL_PASSWORD, _ADMIN_DB))

    return _connect


@pytest.fixture
def data_connection_factory(
    migrated_database: None, db_host_port: tuple[str, int]
) -> Callable[[], psycopg.Connection]:
    host, port = db_host_port

    def _connect() -> psycopg.Connection:
        return psycopg.connect(_dsn(host, port, DATA_ROLE, DATA_PASSWORD, _ADMIN_DB))

    return _connect
