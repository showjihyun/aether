"""spec 0004 2.4, D-4: `IngestionStatusConsumer` — `aether:knowledge:ingestions:status`
소비자(`StatusConsumer` 와 같은 모양, spec 0002 2.4, 2.18, D-2). 실제 Redis
(testcontainers) 위에서 검증합니다.

이 테스트는 **상태 스트림 왕복(worker→api)** 을 걸어 두는 자리입니다 — 2026-10-09
리뷰 반려(변이 증거 8번)에서, 처음 보고에는 `IngestionStatusConsumer` 를 Redis
위에서 직접 검증하는 테스트가 **없다는 것**이 드러났습니다(`test_knowledge_api.py`
는 선언 경로만, `test_apply_ingestion_status.py` 는 fake store 로 usecase만 봤고
소비자 자체는 아무도 부르지 않았습니다). 이 파일이 그 공백을 채웁니다.
"""

from __future__ import annotations

import threading
from uuid import uuid4

import pytest
from aether_api.adapters.inbound.stream.ingestion_status_consumer import (
    IngestionStatusConsumer,
    ensure_group,
)
from aether_api.domain.knowledge_ingestion_status_message import KnowledgeIngestionStatusMessage
from redis import Redis

from tests.support.waiting import wait_until

pytestmark = pytest.mark.integration

_STREAM = "aether:knowledge:ingestions:status"
_GROUP = "aether-api"
_JOIN_TIMEOUT = 5.0


class _FakeApplyIngestionStatus:
    def __init__(self, *, result: bool = True) -> None:
        self.calls: list[KnowledgeIngestionStatusMessage] = []
        self._result = result

    def __call__(self, message: KnowledgeIngestionStatusMessage) -> bool:
        self.calls.append(message)
        return self._result


def test_message_is_parsed_applied_and_acked(redis_client: Redis) -> None:
    ensure_group(redis_client, _STREAM, _GROUP)
    ingestion_id = uuid4()
    redis_client.xadd(
        _STREAM,
        {
            "ingestion_id": str(ingestion_id),
            "status": "succeeded",
            "at": "2026-01-01T00:00:00+00:00",
            "finished_at": "2026-01-01T00:00:01+00:00",
        },
    )

    apply = _FakeApplyIngestionStatus()
    stop = threading.Event()
    consumer = IngestionStatusConsumer(
        redis_client, apply, stream=_STREAM, group=_GROUP, consumer="api-a", block_ms=200
    )
    thread = threading.Thread(target=consumer.run_until, args=(stop,))
    thread.start()
    try:
        applied = wait_until(lambda: len(apply.calls) == 1, timeout=_JOIN_TIMEOUT)
        assert applied, "5초 안에 메시지가 적용되지 않았습니다"
    finally:
        stop.set()
        thread.join(_JOIN_TIMEOUT)

    assert not thread.is_alive()
    assert apply.calls[0].ingestion_id == ingestion_id
    assert apply.calls[0].status == "succeeded"
    summary = redis_client.xpending(_STREAM, _GROUP)
    assert summary["pending"] == 0


def test_malformed_message_is_acked_without_calling_apply(redis_client: Redis) -> None:
    ensure_group(redis_client, _STREAM, _GROUP)
    redis_client.xadd(_STREAM, {"status": "succeeded"})  # ingestion_id, at 누락

    apply = _FakeApplyIngestionStatus()
    stop = threading.Event()
    consumer = IngestionStatusConsumer(
        redis_client, apply, stream=_STREAM, group=_GROUP, consumer="api-b", block_ms=200
    )
    thread = threading.Thread(target=consumer.run_until, args=(stop,))
    thread.start()
    try:

        def _acked() -> bool:
            summary = redis_client.xpending(_STREAM, _GROUP)
            return summary is not None and int(summary["pending"]) == 0

        acked = wait_until(_acked, timeout=_JOIN_TIMEOUT)
        assert acked, "5초 안에 독약 메시지가 ack 되지 않았습니다"
    finally:
        stop.set()
        thread.join(_JOIN_TIMEOUT)

    assert apply.calls == []
