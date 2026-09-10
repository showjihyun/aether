"""`AETHER_` 접두사 환경변수 설정. 기본값만으로 뜹니다.

패키지 루트에 둡니다 — domain·application·adapters 어느 층도 아니므로
architecture.md 3.1 의 층 규칙에 묶이지 않습니다.
"""

from __future__ import annotations

import socket

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def _default_consumer() -> str:
    """consumer 이름의 기본값: hostname. 여러 worker 인스턴스를 구분하기 위함입니다."""
    return socket.gethostname()


class Settings(BaseSettings):
    """환경변수만으로 채워집니다. `.env` 파일을 읽지 않습니다 — 컨테이너 환경변수가 정본입니다."""

    model_config = SettingsConfigDict(env_prefix="AETHER_", extra="ignore")

    version: str = "dev"

    redis_url: str = "redis://localhost:6379/0"
    """spec 2.3. Redis Streams 큐가 있는 곳."""

    worker_stream: str = "aether:runs:requested"
    """spec 2.3: Control → Data. worker 가 consumer group 으로 대기하는 스트림."""

    worker_status_stream: str = "aether:runs:status"
    """spec 2.3: Data → Control. Phase 0 에서는 이름만 예약(P1-5 가 씀)."""

    worker_group: str = "aether-worker"

    worker_consumer: str = Field(default_factory=_default_consumer)

    worker_connect_max_attempts: int = 10
    """Redis 연결 재시도 최대 횟수. 이 횟수를 넘기면 명확한 오류로 종료합니다."""

    worker_connect_base_delay: float = 0.5
    """지수 백오프의 첫 지연(초)."""

    worker_connect_max_delay: float = 8.0
    """지수 백오프의 상한(초)."""
