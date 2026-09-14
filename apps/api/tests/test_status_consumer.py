"""spec 0002 2.4, 2.18, D-2 (P1-5b): `StatusConsumer` — `aether:runs:status` 소비자.

api consumer group `aether-api`. 순서는 자기 PEL 먼저(`XREADGROUP … 0`) → `XREADGROUP
">"` 새 메시지. 메시지를 `RunStatusMessage` 로 파싱해 `ApplyRunStatus` 를 부르고,
적용 여부(`True`/`False`)와 무관하게 DB 커밋 뒤 `XACK` 합니다(D-2, 멱등 무시). 파싱
실패는 WARNING 로그와 함께 즉시 ack(handler 를 부르지 않음). 실제 Redis
(testcontainers) 위에서 검증합니다.
"""

from __future__ import annotations

import threading
from uuid import uuid4

import pytest
from aether_api.adapters.inbound.stream.status_consumer import StatusConsumer, ensure_group
from aether_api.domain.run_status_message import RunStatusMessage
from aether_runtime.domain.run import RunStatus
from redis import Redis

from tests.support.waiting import wait_until

pytestmark = pytest.mark.integration

_STREAM = "aether:runs:status"
_GROUP = "aether-api"
_JOIN_TIMEOUT = 5.0


class _FakeApplyRunStatus:
    """`ApplyRunStatus` 포트의 계측용 fake — 호출된 메시지를 순서대로 기록합니다."""

    def __init__(self, *, result: bool = True) -> None:
        self.calls: list[RunStatusMessage] = []
        self._result = result

    def __call__(self, message: RunStatusMessage) -> bool:
        self.calls.append(message)
        return self._result


def test_message_is_parsed_applied_and_acked(redis_client: Redis) -> None:
    ensure_group(redis_client, _STREAM, _GROUP)
    run_id = uuid4()
    redis_client.xadd(
        _STREAM,
        {
            "run_id": str(run_id),
            "seq": "1",
            "status": "running",
            "at": "2026-01-01T00:00:00+00:00",
        },
    )

    apply = _FakeApplyRunStatus()
    stop = threading.Event()
    consumer = StatusConsumer(
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
    assert apply.calls[0].run_id == run_id
    assert apply.calls[0].seq == 1
    assert apply.calls[0].status == RunStatus.RUNNING
    summary = redis_client.xpending(_STREAM, _GROUP)
    assert summary["pending"] == 0


def test_own_pending_entries_are_processed_before_new_messages(redis_client: Redis) -> None:
    consumer_name = "api-a"
    ensure_group(redis_client, _STREAM, _GROUP)

    first_run = uuid4()
    redis_client.xadd(
        _STREAM,
        {
            "run_id": str(first_run),
            "seq": "1",
            "status": "running",
            "at": "2026-01-01T00:00:00+00:00",
        },
    )
    # 이전 프로세스가 읽고 죽었다고 가정 -- 같은 consumer 이름으로 미리 읽어 PEL 에 남깁니다.
    redis_client.xreadgroup(
        groupname=_GROUP, consumername=consumer_name, streams={_STREAM: ">"}, count=1
    )

    second_run = uuid4()
    redis_client.xadd(
        _STREAM,
        {
            "run_id": str(second_run),
            "seq": "1",
            "status": "running",
            "at": "2026-01-01T00:00:00+00:00",
        },
    )

    apply = _FakeApplyRunStatus()
    stop = threading.Event()
    consumer = StatusConsumer(
        redis_client, apply, stream=_STREAM, group=_GROUP, consumer=consumer_name, block_ms=200
    )
    thread = threading.Thread(target=consumer.run_until, args=(stop,))
    thread.start()
    try:
        done = wait_until(lambda: len(apply.calls) == 2, timeout=_JOIN_TIMEOUT)
        assert done, "5초 안에 두 메시지를 처리하지 못했습니다"
    finally:
        stop.set()
        thread.join(_JOIN_TIMEOUT)

    assert not thread.is_alive()
    assert [message.run_id for message in apply.calls] == [first_run, second_run]


def test_message_with_missing_fields_is_acked_without_calling_apply(redis_client: Redis) -> None:
    ensure_group(redis_client, _STREAM, _GROUP)
    redis_client.xadd(_STREAM, {"run_id": str(uuid4())})  # seq/status/at 누락

    apply = _FakeApplyRunStatus()
    stop = threading.Event()
    consumer = StatusConsumer(
        redis_client, apply, stream=_STREAM, group=_GROUP, consumer="api-a", block_ms=200
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
    assert apply.calls == []


def test_applied_false_is_still_acked(redis_client: Redis) -> None:
    """spec D-2: 이미 적용된(낮은/같은 `seq`) 메시지는 `apply` 가 `False` 를 돌려줘도
    ack 합니다 — 멱등 무시입니다."""
    ensure_group(redis_client, _STREAM, _GROUP)
    run_id = uuid4()
    redis_client.xadd(
        _STREAM,
        {
            "run_id": str(run_id),
            "seq": "1",
            "status": "running",
            "at": "2026-01-01T00:00:00+00:00",
        },
    )

    apply = _FakeApplyRunStatus(result=False)
    stop = threading.Event()
    consumer = StatusConsumer(
        redis_client, apply, stream=_STREAM, group=_GROUP, consumer="api-a", block_ms=200
    )
    thread = threading.Thread(target=consumer.run_until, args=(stop,))
    thread.start()
    try:
        acked = wait_until(
            lambda: redis_client.xpending(_STREAM, _GROUP)["pending"] == 0, timeout=_JOIN_TIMEOUT
        )
        assert acked
    finally:
        stop.set()
        thread.join(_JOIN_TIMEOUT)

    assert not thread.is_alive()
    assert len(apply.calls) == 1
