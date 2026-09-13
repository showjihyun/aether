"""spec 0002 2.14, R-13 (spec 0001 개정 8 이월): `Heartbeat` — worker 의 생존을
Redis 키로 알립니다. compose 의 healthcheck 가 `aether:worker:{consumer}:heartbeat`
의 존재를 확인합니다(`redis-cli` 가 이미지에 없어 `python -c` 로 직접 확인, spec
2.14).
"""

from __future__ import annotations

from datetime import UTC, datetime

from redis import Redis


class Heartbeat:
    """`key` 를 `beat()` 마다 현재 시각(ISO 8601)으로 `SET … EX ttl_seconds` 합니다."""

    def __init__(self, client: Redis, key: str, ttl_seconds: float) -> None:
        self._client = client
        self._key = key
        self._ttl_seconds = ttl_seconds

    def beat(self) -> None:
        self._client.set(self._key, datetime.now(UTC).isoformat(), ex=int(self._ttl_seconds))
