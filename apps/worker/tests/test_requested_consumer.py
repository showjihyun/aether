"""spec 0002 2.4, 2.18, D-10 (P1-5a): `RequestedConsumer` — `aether:runs:requested`
소비자. 실제 Redis(testcontainers) 위에서 검증합니다.

순서는 (a) 재시작 시 자기 PEL 먼저(`XREADGROUP … 0`), (b) 그 뒤 `XAUTOCLAIM`(다른
consumer 가 두고 간 오래된 메시지 회수, `min_idle_ms` 를 0 으로 주입해 즉시
가로채기), (c) `ack=False`(`LeaseHeld`) 는 PEL 에 남김, (d) 필드 누락은 ack 하고
handler 를 부르지 않음(독약 메시지), (e) 매 단계 `count=1` — handler 호출은
한 번에 하나씩입니다.
"""

from __future__ import annotations

import threading
from typing import Any
from uuid import UUID, uuid4

import pytest
from aether_worker.adapters.inbound.stream.requested_consumer import (
    RequestedConsumer,
    ensure_group,
)
from aether_worker.application.ports.inbound.handle_run_requested import (
    HandleOutcome,
    RequestedMessage,
)
from redis import Redis

from tests.support.waiting import wait_until

pytestmark = pytest.mark.integration

_STREAM = "aether:runs:requested"
_GROUP = "aether-worker"
_JOIN_TIMEOUT = 5.0


class _CountSpy:
    """`xreadgroup`/`xautoclaim` 에 실제로 건네진 `count` 를 기록하는 얇은 프록시.

    나머지 호출은 그대로 실제 클라이언트에 위임합니다 — `RequestedConsumer` 가
    이 프록시를 진짜 `Redis` 처럼 쓸 수 있어야 합니다.
    """

    def __init__(self, client: Redis) -> None:
        self._client = client
        self.counts: list[int | None] = []

    def xreadgroup(
        self,
        groupname: str,
        consumername: str,
        streams: Any,
        count: int | None = None,
        block: int | None = None,
    ) -> Any:
        self.counts.append(count)
        return self._client.xreadgroup(
            groupname=groupname,
            consumername=consumername,
            streams=streams,
            count=count,
            block=block,
        )

    def xautoclaim(
        self,
        name: Any,
        groupname: Any,
        consumername: Any,
        min_idle_time: int,
        start_id: Any = "0-0",
        count: int | None = None,
    ) -> Any:
        self.counts.append(count)
        return self._client.xautoclaim(
            name=name,
            groupname=groupname,
            consumername=consumername,
            min_idle_time=min_idle_time,
            start_id=start_id,
            count=count,
        )

    def xack(self, name: Any, groupname: Any, *ids: Any) -> Any:
        return self._client.xack(name, groupname, *ids)


def test_own_pending_entries_are_processed_before_new_messages(redis_client: Redis) -> None:
    consumer_name = "worker-a"
    ensure_group(redis_client, _STREAM, _GROUP)

    first_run, first_agent_version = uuid4(), uuid4()
    redis_client.xadd(
        _STREAM, {"run_id": str(first_run), "agent_version_id": str(first_agent_version)}
    )
    # 이전 실행이 이 메시지를 읽고 죽었다고 가정 — 같은 이름으로 미리 읽어 PEL 에 남깁니다.
    redis_client.xreadgroup(
        groupname=_GROUP, consumername=consumer_name, streams={_STREAM: ">"}, count=1
    )

    second_run, second_agent_version = uuid4(), uuid4()
    redis_client.xadd(
        _STREAM, {"run_id": str(second_run), "agent_version_id": str(second_agent_version)}
    )

    processed: list[UUID] = []
    stop = threading.Event()

    def handler(message: RequestedMessage) -> HandleOutcome:
        processed.append(message.run_id)
        if len(processed) >= 2:
            stop.set()
        return HandleOutcome(ack=True, status=None)

    consumer = RequestedConsumer(
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
    thread.join(_JOIN_TIMEOUT)

    assert not thread.is_alive(), "5초 안에 두 메시지를 처리하지 못했습니다"
    assert processed == [first_run, second_run]


def test_xautoclaim_reclaims_a_message_left_pending_by_another_consumer(
    redis_client: Redis,
) -> None:
    ensure_group(redis_client, _STREAM, _GROUP)
    run_id, agent_version_id = uuid4(), uuid4()
    redis_client.xadd(_STREAM, {"run_id": str(run_id), "agent_version_id": str(agent_version_id)})
    # "other-worker" 가 읽고 ack 하지 않은 채 죽었다고 가정.
    redis_client.xreadgroup(
        groupname=_GROUP, consumername="other-worker", streams={_STREAM: ">"}, count=1
    )

    stop = threading.Event()
    processed: list[UUID] = []

    def handler(message: RequestedMessage) -> HandleOutcome:
        processed.append(message.run_id)
        stop.set()
        return HandleOutcome(ack=True, status=None)

    consumer = RequestedConsumer(
        redis_client,
        stream=_STREAM,
        group=_GROUP,
        consumer="me",
        handler=handler,
        xautoclaim_min_idle_ms=0,
        block_ms=200,
    )
    thread = threading.Thread(target=consumer.run_until, args=(stop,))
    thread.start()
    thread.join(_JOIN_TIMEOUT)

    assert not thread.is_alive()
    assert processed == [run_id]
    summary = redis_client.xpending(_STREAM, _GROUP)
    assert summary["pending"] == 0, "가로챈 메시지는 ack 되어야 합니다"


def test_lease_held_outcome_leaves_the_message_pending(redis_client: Redis) -> None:
    ensure_group(redis_client, _STREAM, _GROUP)
    run_id, agent_version_id = uuid4(), uuid4()
    redis_client.xadd(_STREAM, {"run_id": str(run_id), "agent_version_id": str(agent_version_id)})

    stop = threading.Event()

    def handler(message: RequestedMessage) -> HandleOutcome:
        stop.set()
        return HandleOutcome(ack=False, status=None)

    consumer = RequestedConsumer(
        redis_client,
        stream=_STREAM,
        group=_GROUP,
        consumer="me",
        handler=handler,
        xautoclaim_min_idle_ms=0,
        block_ms=200,
    )
    thread = threading.Thread(target=consumer.run_until, args=(stop,))
    thread.start()
    thread.join(_JOIN_TIMEOUT)

    assert not thread.is_alive()
    summary = redis_client.xpending(_STREAM, _GROUP)
    assert summary["pending"] == 1, "ack=False 인 메시지는 PEL 에 남아야 합니다"


def test_message_with_missing_fields_is_acked_without_calling_the_handler(
    redis_client: Redis,
) -> None:
    ensure_group(redis_client, _STREAM, _GROUP)
    redis_client.xadd(_STREAM, {"run_id": str(uuid4())})  # agent_version_id 누락

    stop = threading.Event()
    handler_calls: list[RequestedMessage] = []

    def handler(message: RequestedMessage) -> HandleOutcome:
        handler_calls.append(message)
        return HandleOutcome(ack=True, status=None)

    consumer = RequestedConsumer(
        redis_client,
        stream=_STREAM,
        group=_GROUP,
        consumer="me",
        handler=handler,
        xautoclaim_min_idle_ms=0,
        block_ms=200,
    )
    thread = threading.Thread(target=consumer.run_until, args=(stop,))
    thread.start()
    try:
        acked = wait_until(
            lambda: redis_client.xpending(_STREAM, _GROUP)["pending"] == 0, timeout=_JOIN_TIMEOUT
        )
        assert acked, "필드 누락 메시지는 결국 ack 되어야 합니다"
    finally:
        stop.set()
        thread.join(_JOIN_TIMEOUT)

    assert not thread.is_alive()
    assert handler_calls == []


def test_reads_and_claims_are_always_count_one(redis_client: Redis) -> None:
    ensure_group(redis_client, _STREAM, _GROUP)
    run_id, agent_version_id = uuid4(), uuid4()
    redis_client.xadd(_STREAM, {"run_id": str(run_id), "agent_version_id": str(agent_version_id)})

    spy = _CountSpy(redis_client)
    stop = threading.Event()

    def handler(message: RequestedMessage) -> HandleOutcome:
        stop.set()
        return HandleOutcome(ack=True, status=None)

    consumer = RequestedConsumer(
        spy,
        stream=_STREAM,
        group=_GROUP,
        consumer="me",
        handler=handler,
        xautoclaim_min_idle_ms=0,
        block_ms=200,
    )
    thread = threading.Thread(target=consumer.run_until, args=(stop,))
    thread.start()
    thread.join(_JOIN_TIMEOUT)

    assert not thread.is_alive()
    assert spy.counts, "xreadgroup/xautoclaim 이 한 번도 불리지 않았습니다"
    assert set(spy.counts) == {1}, f"count=1 이 아닌 호출이 있습니다: {spy.counts}"
