"""spec 0001 2.9 H-3: `Settings.psycopg_dsn` — `+psycopg` 드라이버 표기만 벗깁니다.

`PostgresApiKeyStore` 는 psycopg 로 직접 연결하므로 SQLAlchemy 형식(`+psycopg`)이 아니라
libpq 형식(`postgresql://`)이 필요합니다. `Settings.database_url` 은 계속 SQLAlchemy
형식을 기본값으로 두므로(alembic 이 그 형식을 읽음, spec 2.8), 벗기는 변환을 한 곳에
둡니다.
"""

from __future__ import annotations

from aether_api.settings import Settings


def test_psycopg_dsn_strips_psycopg_driver_suffix() -> None:
    settings = Settings(database_url="postgresql+psycopg://u:p@h:5432/db")

    assert settings.psycopg_dsn == "postgresql://u:p@h:5432/db"


def test_psycopg_dsn_passes_through_already_libpq_url() -> None:
    settings = Settings(database_url="postgresql://u:p@h:5432/db")

    assert settings.psycopg_dsn == "postgresql://u:p@h:5432/db"
