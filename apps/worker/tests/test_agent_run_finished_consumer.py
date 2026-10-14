"""spec 0005 2.5 개정 3 (P4-2a B2): `AgentRunFinishedConsumer` -- 빠른 경로. `aether:runs:status` 를
Workflow 전용 consumer group `aether-workflow` 로 읽는다. 실제 Redis.

Agent Run 의 api 쪽 투영 group(`aether-api`)과 **다른 group** 이다 -- 같은 스트림의 같은 메시지를
각자 한 번씩 받는다. 증명하는 것: 종결 상태만 재개 유스케이스를 부르고, 미종결·파싱 실패는 즉시 ack,
유스케이스가 실패해도 스레드가 죽지 않으며 ack 하지 않는다(스위퍼가 구한다), 다른 group 의 소비를
건드리지 않는다.
"""

from __future__ import annotations

import threading
from uuid import UUID, uuid4

import pytest
from aether_worker.adapters.inbound.stream.agent_run_finished_consumer import (
    AgentRunFinishedConsumer,
)
from aether_worker.adapters.inbound.stream.requested_consumer import ensure_group
from redis import Redis

from tests.support.waiting import wait_until

pytestmark = pytest.mark.integration

_STREAM = "aether:runs:status"
_GROUP = "aether-workflow"
_OTHER_GROUP = "aether-api"
_JOIN_TIMEOUT = 5.0


class _Resume:
    def __init__(self, *, fail_on: UUID | None = None) -> None:
        self.finished: list[UUID] = []
        self._fail_on = fail_on

    def on_agent_run_finished(self, agent_run_id: UUID) -> int:
        if agent_run_id == self._fail_on:
            raise ConnectionError("db down")
        self.finished.append(agent_run_id)
        return 1

    def sweep(self) -> int:
        return 0


def _status(client: Redis, run_id: UUID, status: str) -> None:
    client.xadd(
        _STREAM,
        {"run_id": str(run_id), "seq": "3", "status": status, "at": "2026-10-14T12:00:00+00:00"},
    )


def _pending(client: Redis, group: str) -> int:
    return int(client.xpending(_STREAM, group)["pending"])


def _start(
    client: Redis, resume: _Resume, name: str | None = None
) -> tuple[threading.Event, threading.Thread]:
    stop = threading.Event()
    consumer = AgentRunFinishedConsumer(
        client,
        stream=_STREAM,
        group=_GROUP,
        consumer=name or f"c-{uuid4()}",
        resume=resume,
        block_ms=100,
    )
    thread = threading.Thread(target=consumer.run_until, args=(stop,), daemon=True)
    thread.start()
    return stop, thread


def test_only_terminal_statuses_wake_and_every_message_is_acked(redis_client: Redis) -> None:
    ensure_group(redis_client, _STREAM, _GROUP)
    terminal = {s: uuid4() for s in ("succeeded", "failed", "cancelled", "timed_out")}
    ignored = [uuid4() for _ in range(3)]
    for status, run_id in terminal.items():
        _status(redis_client, run_id, status)
    for run_id, status in zip(ignored, ("queued", "running", "waiting"), strict=True):
        _status(redis_client, run_id, status)
    resume = _Resume()

    stop, thread = _start(redis_client, resume)
    try:
        assert wait_until(
            lambda: len(resume.finished) == 4 and _pending(redis_client, _GROUP) == 0,
            timeout=_JOIN_TIMEOUT,
        ), "종결 넷이 모두 재개 유스케이스에 닿고 일곱 메시지가 모두 ack 되어야 한다"
    finally:
        stop.set()
        thread.join(_JOIN_TIMEOUT)

    assert set(resume.finished) == set(terminal.values())
    assert not set(resume.finished) & set(ignored)


def test_malformed_messages_are_acked_without_waking(redis_client: Redis) -> None:
    ensure_group(redis_client, _STREAM, _GROUP)
    redis_client.xadd(_STREAM, {"status": "succeeded"})  # run_id 없음
    redis_client.xadd(_STREAM, {"run_id": "not-a-uuid", "status": "succeeded"})
    redis_client.xadd(_STREAM, {"run_id": str(uuid4()), "status": "exploded"})
    resume = _Resume()

    stop, thread = _start(redis_client, resume)
    try:
        assert wait_until(lambda: _pending(redis_client, _GROUP) == 0, timeout=_JOIN_TIMEOUT)
    finally:
        stop.set()
        thread.join(_JOIN_TIMEOUT)

    assert resume.finished == []


def test_a_failing_use_case_leaves_the_message_pending_and_the_thread_alive(
    redis_client: Redis,
) -> None:
    """DB 장애로 재큐하지 못한 신호는 ack 하지 않는다(스위퍼가 구한다). 그리고 **스레드는 죽지
    않는다** -- 죽으면 그 뒤의 신호가 전부 소리 없이 사라진다."""
    ensure_group(redis_client, _STREAM, _GROUP)
    broken, healthy = uuid4(), uuid4()
    _status(redis_client, broken, "succeeded")
    _status(redis_client, healthy, "failed")
    resume = _Resume(fail_on=broken)

    stop, thread = _start(redis_client, resume)
    try:
        assert wait_until(lambda: resume.finished == [healthy], timeout=_JOIN_TIMEOUT), (
            "첫 메시지가 실패해도 다음 메시지를 처리해야 한다"
        )
        assert thread.is_alive()
        assert _pending(redis_client, _GROUP) == 1
    finally:
        stop.set()
        thread.join(_JOIN_TIMEOUT)


def test_a_restarted_consumer_retries_its_own_pending_message(redis_client: Redis) -> None:
    """ack 하지 못한 메시지는 PEL 에 남고, 같은 consumer 이름으로 다시 뜨면 먼저 비운다."""
    ensure_group(redis_client, _STREAM, _GROUP)
    run_id = uuid4()
    _status(redis_client, run_id, "succeeded")
    name = f"c-{uuid4()}"

    stop, thread = _start(redis_client, _Resume(fail_on=run_id), name)
    try:
        assert wait_until(lambda: _pending(redis_client, _GROUP) == 1, timeout=_JOIN_TIMEOUT)
    finally:
        stop.set()
        thread.join(_JOIN_TIMEOUT)

    second = _Resume()
    stop, thread = _start(redis_client, second, name)
    try:
        assert wait_until(
            lambda: second.finished == [run_id] and _pending(redis_client, _GROUP) == 0,
            timeout=_JOIN_TIMEOUT,
        )
    finally:
        stop.set()
        thread.join(_JOIN_TIMEOUT)


def test_the_workflow_group_does_not_consume_the_api_projection_group(
    redis_client: Redis,
) -> None:
    """같은 스트림을 다른 group 으로 읽는다 -- Agent Run 의 투영 group 은 이 소비자가 아무 것도
    가져가지 않고, 자기 몫(3건 미처리)을 그대로 가진다."""
    ensure_group(redis_client, _STREAM, _GROUP)
    ensure_group(redis_client, _STREAM, _OTHER_GROUP)
    for _ in range(3):
        _status(redis_client, uuid4(), "succeeded")
    resume = _Resume()

    stop, thread = _start(redis_client, resume)
    try:
        assert wait_until(lambda: len(resume.finished) == 3, timeout=_JOIN_TIMEOUT)
    finally:
        stop.set()
        thread.join(_JOIN_TIMEOUT)

    groups = {g["name"]: g for g in redis_client.xinfo_groups(_STREAM)}
    assert groups[_OTHER_GROUP]["pending"] == 0
    assert groups[_OTHER_GROUP]["lag"] == 3, "api 투영 group 은 한 건도 읽히지 않았다"
