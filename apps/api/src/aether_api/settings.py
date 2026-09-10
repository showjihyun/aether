"""`AETHER_` 접두사 환경변수 설정. 기본값만으로 뜹니다.

패키지 루트에 둡니다 — domain·application·adapters 어느 층도 아니므로
architecture.md 3.1 의 층 규칙에 묶이지 않습니다.
"""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """환경변수만으로 채워집니다. `.env` 파일을 읽지 않습니다 — 컨테이너 환경변수가 정본입니다."""

    model_config = SettingsConfigDict(env_prefix="AETHER_", extra="ignore")

    version: str = "dev"

    database_url: str = "postgresql+psycopg://aether:aether@localhost:5432/aether"
    """spec 2.8. `apps/api/migrations/env.py` 가 기본으로 읽는 DB 접속 문자열
    (`ALEMBIC_URL` 환경변수가 있으면 그것이 우선). 관리자 역할로 접속합니다 —
    런타임 역할(`aether_control`)과는 다릅니다."""
