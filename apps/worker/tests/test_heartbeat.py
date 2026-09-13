"""spec 0002 2.14, R-13 (P1-5a): `Heartbeat` — `aether:worker:{consumer}:heartbeat`
키를 TTL 로 `SET` 합니다. compose 의 healthcheck 가 이 키의 존재를 확인합니다
(spec 0001 개정 8 이월).

두 번째 `beat()` 가 TTL 을 갱신하는지는 `sleep` 으로 기다리지 않고, 관리자 명령
(`EXPIRE`)으로 첫 TTL 을 짧게 만든 뒤 재비교해 결정적으로 증명합니다
(`test_run_state_store_contract.py` 가 lease 만료를 재현하는 것과 같은 방식).
"""

from __future__ import annotations

import pytest
from aether_worker.adapters.outbound.redis.heartbeat import Heartbeat
from redis import Redis

pytestmark = pytest.mark.integration


def test_beat_sets_the_key_with_a_ttl(redis_client: Redis) -> None:
    key = "aether:worker:test-1:heartbeat"
    heartbeat = Heartbeat(redis_client, key, ttl_seconds=15)

    heartbeat.beat()

    assert redis_client.exists(key) == 1
    ttl = redis_client.ttl(key)
    assert 0 < ttl <= 15


def test_second_beat_renews_the_ttl(redis_client: Redis) -> None:
    key = "aether:worker:test-2:heartbeat"
    heartbeat = Heartbeat(redis_client, key, ttl_seconds=15)
    heartbeat.beat()
    redis_client.expire(key, 1)  # 관리자 명령으로 짧게 만듭니다 — sleep 없이 재현.
    shrunk_ttl = redis_client.ttl(key)
    assert shrunk_ttl <= 1

    heartbeat.beat()

    renewed_ttl = redis_client.ttl(key)
    assert renewed_ttl > shrunk_ttl
