"""`AETHER_` 접두사 환경변수 설정. 기본값만으로 뜹니다.

패키지 루트에 둡니다 — domain·application·adapters 어느 층도 아니므로
architecture.md 3.1 의 층 규칙에 묶이지 않습니다.
"""

from __future__ import annotations

import socket
from typing import Literal

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

    database_url: str = "postgresql+psycopg://aether:aether@localhost:5432/aether"
    """spec 0002 2.15. worker 가 처음으로 DB 를 씁니다 — `data.run_executions`·
    `data.run_states` 쓰기, `control.runs`·`agent_versions` 읽기. compose 에서는
    `aether_data` 역할 URL(api 의 같은 이름 변수는 `aether_control` — 역할이
    다릅니다)."""

    @property
    def psycopg_dsn(self) -> str:
        """`database_url` 에서 `+psycopg` 드라이버 표기(SQLAlchemy 형식)만 벗깁니다
        (`apps/api/src/aether_api/settings.py` 와 같은 구현)."""
        return self.database_url.replace("postgresql+psycopg://", "postgresql://", 1)

    model_adapter: Literal["fake", "openai_compatible"] = "fake"
    """spec 0002 2.5, 2.15. `fake` 가 기본 — 판정(verify·smoke)은 항상 네트워크 없이."""

    model_base_url: str | None = None
    """`model_adapter=openai_compatible` 일 때만 씁니다. compose `llm` 프로파일 안에서는
    `http://llm:11434/v1`."""

    model_id: str = "qwen3.8:27b"
    """`definition.model.id` 가 `null` 일 때 쓰는 기본 모델(spec 0002 D-1)."""

    model_api_key: str | None = None
    """선택. 비밀값 — 로그·코드에 남기지 않습니다."""

    model_thinking: bool = False
    """spec 0002 D-19. Qwen3.8 계열은 기본이 thinking 이라 꺼 둡니다."""

    observation_max_chars: int = 16_000
    """spec 0002 2.6, R-14. 도구 결과를 이 길이로 잘라 `truncated: true` 를 표시합니다."""

    events_maxlen: int = 10_000
    """spec 0002 2.7. Run 이벤트 스트림의 근사 `MAXLEN`."""

    events_ttl_seconds: int = 86_400
    """spec 0002 2.7. Run 종결 뒤 이벤트 스트림의 TTL(초)."""

    worker_lease_seconds: float = 60.0
    """spec 0002 2.4, D-10. 실행 권한 lease 의 TTL — 단계마다 갱신합니다."""

    worker_xautoclaim_min_idle_ms: int = 3_900_000
    """spec 0002 2.4, D-10. `timeout` 상한(3600 초) + 300 초 여유. 테스트는 0 을 주입해
    가로채기 경로를 즉시 실행합니다."""

    worker_heartbeat_seconds: float = 5.0
    """spec 0002 2.14, R-13. 이 간격마다 heartbeat 키를 갱신합니다(TTL 은 이 값의 3배)."""
