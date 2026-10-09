"""spec 0004 2.4, D-4: `IngestionRequestedConsumer` — `aether:knowledge:ingestions:
requested` 소비자. 실제 Redis(testcontainers) 위에서 검증합니다(`RequestedConsumer`
와 같은 패턴, P1-5a).

(a) 재시작 시 자기 PEL 먼저, (b) 필드 누락은 ack 하고 handler 를 부르지 않음
(독약 메시지), (c) 정상 메시지는 파싱되어 handler 가 불리고 ack 됩니다.
"""

from __future__ import annotations

import threading
from uuid import uuid4

import pytest
from aether_worker.adapters.inbound.stream.ingestion_requested_consumer import (
    IngestionRequestedConsumer,
    ensure_group,
)
from aether_worker.application.ports.inbound.handle_ingestion_requested import (
    HandleIngestionOutcome,
    IngestionRequestedMessage,
)
from redis import Redis

from tests.support.waiting import wait_until

pytestmark = pytest.mark.integration

_STREAM = "aether:knowledge:ingestions:requested"
_GROUP = "aether-worker"
_JOIN_TIMEOUT = 5.0


def test_own_pending_entries_are_processed_before_new_messages(redis_client: Redis) -> None:
    consumer_name = "worker-a"
    ensure_group(redis_client, _STREAM, _GROUP)

    first_ingestion, first_set = uuid4(), uuid4()
    redis_client.xadd(
        _STREAM,
        {"ingestion_id": str(first_ingestion), "knowledge_set_id": str(first_set), "source": "/a"},
    )
    # 이전 실행이 이 메시지를 읽고 죽었다고 가정 — 같은 이름으로 미리 읽어 PEL 에 남깁니다.
    redis_client.xreadgroup(
        groupname=_GROUP, consumername=consumer_name, streams={_STREAM: ">"}, count=1
    )

    second_ingestion, second_set = uuid4(), uuid4()
    redis_client.xadd(
        _STREAM,
        {
            "ingestion_id": str(second_ingestion),
            "knowledge_set_id": str(second_set),
            "source": "/b",
        },
    )

    processed: list[str] = []
    stop = threading.Event()

    def handler(message: IngestionRequestedMessage) -> HandleIngestionOutcome:
        processed.append(message.source)
        if len(processed) == 2:
            stop.set()
        return HandleIngestionOutcome(ack=True)

    consumer = IngestionRequestedConsumer(
        redis_client,
        stream=_STREAM,
        group=_GROUP,
        consumer=consumer_name,
        handler=handler,
        xautoclaim_min_idle_ms=0,
        block_ms=200,
    )
    thread = threading.Thread(target=consumer.run_until, args=(stop,))
    thread.start()
    try:
        assert wait_until(lambda: len(processed) == 2, timeout=5.0)
    finally:
        stop.set()
        thread.join(_JOIN_TIMEOUT)

    assert processed == ["/a", "/b"]


def test_malformed_message_is_acked_without_calling_handler(redis_client: Redis) -> None:
    ensure_group(redis_client, _STREAM, _GROUP)
    redis_client.xadd(_STREAM, {"knowledge_set_id": str(uuid4())})  # ingestion_id, source 누락

    calls: list[IngestionRequestedMessage] = []
    stop = threading.Event()

    def handler(message: IngestionRequestedMessage) -> HandleIngestionOutcome:
        calls.append(message)
        return HandleIngestionOutcome(ack=True)

    consumer = IngestionRequestedConsumer(
        redis_client,
        stream=_STREAM,
        group=_GROUP,
        consumer="worker-b",
        handler=handler,
        xautoclaim_min_idle_ms=0,
        block_ms=200,
    )
    thread = threading.Thread(target=consumer.run_until, args=(stop,))
    thread.start()
    try:

        def _delivered_and_acked() -> bool:
            groups = redis_client.xinfo_groups(_STREAM)
            group_info = next(g for g in groups if g["name"] == _GROUP)
            pending = redis_client.xpending(_STREAM, _GROUP)
            delivered = int(group_info.get("entries-read") or 0) >= 1
            acked = pending is not None and pending["pending"] == 0
            return delivered and acked

        assert wait_until(_delivered_and_acked, timeout=5.0)
    finally:
        stop.set()
        thread.join(_JOIN_TIMEOUT)

    assert calls == []  # 독약 메시지는 handler 를 부르지 않고 즉시 ack 됩니다.
