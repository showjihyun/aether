"""spec 0002 2.15 (P1-5a): worker `Settings` — 새 환경변수의 기본값과 `psycopg_dsn`.

`AETHER_DATABASE_URL` 은 worker 에서 처음 쓰입니다(`aether_data` 역할, api 의 같은
이름 변수와 역할이 다름 — spec 2.15). `psycopg_dsn` 은 `apps/api/src/aether_api/
settings.py` 와 같은 구현입니다.
"""

from __future__ import annotations

import pytest
from aether_worker.settings import Settings
from pydantic import ValidationError


def test_database_url_default_and_psycopg_dsn_strips_the_driver_suffix() -> None:
    settings = Settings()

    assert settings.database_url == "postgresql+psycopg://aether:aether@localhost:5432/aether"
    assert settings.psycopg_dsn == "postgresql://aether:aether@localhost:5432/aether"


def test_model_and_worker_defaults() -> None:
    settings = Settings()

    assert settings.model_adapter == "fake"
    assert settings.model_base_url is None
    assert settings.model_id == "qwen3.8:27b"
    assert settings.model_api_key is None
    assert settings.model_thinking is False
    assert settings.observation_max_chars == 16_000
    assert settings.events_maxlen == 10_000
    assert settings.events_ttl_seconds == 86_400
    assert settings.worker_lease_seconds == 60.0
    assert settings.worker_xautoclaim_min_idle_ms == 3_900_000
    assert settings.worker_heartbeat_seconds == 5.0


def test_model_adapter_rejects_an_invalid_value(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AETHER_MODEL_ADAPTER", "not-a-real-adapter")

    with pytest.raises(ValidationError):
        Settings()
