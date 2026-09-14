"""spec 0002 2.2, 2.18 (P1-5b): `RedisRunNotifier` — `aether:runs:requested` 로
`run_id`·`agent_version_id`·`traceparent` 필드를 `XADD` 합니다. 실제 Redis
(testcontainers) 위에서 검증합니다.

worker 의 `_parse`(`apps/worker/src/aether_worker/adapters/inbound/stream/
requested_consumer.py`)는 `traceparent` 필드를 `fields.get("traceparent")` 로 읽어
없어도(`None`) 파싱에 실패하지 않습니다 — 이 어댑터는 그래도 스트림 계약 표(2.18)의
세 필드를 항상 실어 보냅니다: `traceparent=None` 이면 빈 문자열로 씁니다(P1-8 이
실제 값으로 채울 자리를 비워 둡니다).
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from aether_api.adapters.outbound.redis.run_notifier import RedisRunNotifier
from redis import Redis

pytestmark = pytest.mark.integration

_STREAM = "aether:runs:requested"


def _xrange_all(client: Redis, stream: str) -> list[tuple[str, dict[str, str]]]:
    """`xrange` 의 반환 타입은(redis-py 스텁 상) `bytes | str` 및 `None` 을 허용합니다
    — `decode_responses=True` 로 접속했으므로 런타임에는 항상 `str` 이지만, 정적
    타입은 그것을 모릅니다(`packages/runtime/tests/test_redis_adapters.py` 와 같은
    헬퍼 — 한 번만 단언해 나머지 테스트가 `dict[str, str]` 로 안전하게 인덱싱합니다)."""
    entries = client.xrange(stream, min="-", max="+")
    assert entries is not None
    result: list[tuple[str, dict[str, str]]] = []
    for entry_id, fields in entries:
        assert isinstance(entry_id, str)
        assert fields is not None
        narrowed: dict[str, str] = {}
        for key, value in fields.items():
            assert isinstance(key, str)
            assert isinstance(value, str)
            narrowed[key] = value
        result.append((entry_id, narrowed))
    return result


def test_requested_writes_run_id_and_agent_version_id(redis_client: Redis) -> None:
    notifier = RedisRunNotifier(redis_client)
    run_id, agent_version_id = uuid4(), uuid4()

    notifier.requested(run_id, agent_version_id, "00-trace-01")

    entries = _xrange_all(redis_client, _STREAM)
    assert len(entries) == 1
    _message_id, fields = entries[0]
    assert fields["run_id"] == str(run_id)
    assert fields["agent_version_id"] == str(agent_version_id)
    assert fields["traceparent"] == "00-trace-01"


def test_requested_sends_empty_string_traceparent_when_none(redis_client: Redis) -> None:
    """P1-8 이전에는 api 가 아직 트레이싱이 없어 `None` 을 건넵니다 — 필드 자체는
    항상 실려야(2.18) worker `_parse` 가 파싱할 수 있는 형태를 유지합니다."""
    notifier = RedisRunNotifier(redis_client)
    run_id, agent_version_id = uuid4(), uuid4()

    notifier.requested(run_id, agent_version_id, None)

    entries = _xrange_all(redis_client, _STREAM)
    _message_id, fields = entries[0]
    assert fields["traceparent"] == ""
