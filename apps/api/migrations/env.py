"""Alembic 환경(spec 2.8, plan P0-8 순서 3).

URL 우선순위: `ALEMBIC_URL` 환경변수 > `Settings().database_url`. `alembic.ini`
의 `sqlalchemy.url` 은 자리표시자일 뿐이고 여기서 항상 덮어씁니다. 마이그레이션은
관리자 역할로 실행합니다 — 런타임 역할(`aether_control`, `aether_data`)은 스키마를
만들 권한이 없습니다.
"""

from __future__ import annotations

import os
from logging.config import fileConfig

from aether_api.settings import Settings
from alembic import context
from sqlalchemy import engine_from_config, pool

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = None
"""SQLAlchemy ORM 을 쓰지 않습니다 — 스키마는 이 마이그레이션들이 유일한 정본입니다.
`autogenerate` 는 이 단위의 범위 밖입니다."""


def _database_url() -> str:
    return os.environ.get("ALEMBIC_URL") or Settings().database_url


def run_migrations_offline() -> None:
    """`--sql` 로 SQL 스크립트만 생성할 때. 이 저장소는 지금 쓰지 않습니다."""
    url = _database_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """실제 DB 에 접속해 마이그레이션을 적용합니다. testcontainers 통합 테스트와
    운영 배포가 모두 이 경로를 씁니다."""
    section = config.get_section(config.config_ini_section) or {}
    section["sqlalchemy.url"] = _database_url()

    connectable = engine_from_config(
        section,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
