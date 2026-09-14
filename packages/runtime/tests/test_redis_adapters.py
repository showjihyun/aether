"""spec 0002 2.1, 2.7(개정 2), 2.18 (P1-5a): `RedisEventSink`·`RedisStatusNotifier` 의
포트 계약 — 실제 Redis(testcontainers) 위에서 검증합니다.

`EventSink` 계약(2.7 개정 2)의 핵심은 **같은 `seq` 의 재발행은 성공**입니다 — Redis 는
top ID 이하의 explicit `XADD` 를 `ERR The ID specified in XADD is equal or smaller`
로 거부하므로, 어댑터가 그 오류 문자열만 흡수하고 다른 `ResponseError` 는 그대로
전파해야 합니다(2.4 의 재개, R-16).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from aether_runtime.adapters.outbound.redis.event_sink import RedisEventSink
from aether_runtime.adapters.outbound.redis.status_notifier import RedisStatusNotifier
from aether_runtime.application.ports.outbound.status_notifier import StatusMessage
from aether_runtime.domain.events import EventType, RunEvent
from aether_runtime.domain.failure import FailureReason
from aether_runtime.domain.run import RunStatus
from redis import Redis
from redis.exceptions import ResponseError

pytestmark = pytest.mark.integration


def _xrange_all(client: Redis, stream: str) -> list[tuple[str, dict[str, str]]]:
    """`xrange` 의 반환 타입은(redis-py 스텁 상) `bytes | str` 및 `None` 을 허용합니다
    — `decode_responses=True` 로 접속했으므로 런타임에는 항상 `str` 이지만, 정적
    타입은 그것을 모릅니다. 여기서 한 번만 단언해(런타임 안전성 + 정적 좁히기)
    나머지 테스트가 `dict[str, str]` 로 안전하게 인덱싱할 수 있게 합니다."""
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


def _event(run_id: uuid.UUID, seq: int, event_type: EventType = "run.status") -> RunEvent:
    return RunEvent(
        run_id=run_id,
        seq=seq,
        at=datetime(2026, 1, 1, tzinfo=UTC),
        type=event_type,
        payload={"status": "running"},
    )


def test_publish_uses_explicit_id_seq_dash_zero(redis_client: Redis) -> None:
    run_id = uuid.uuid4()
    sink = RedisEventSink(redis_client)

    sink.publish(_event(run_id, seq=1))

    stream = f"aether:runs:{run_id}:events"
    entries = _xrange_all(redis_client, stream)
    assert [entry_id for entry_id, _ in entries] == ["1-0"]


def test_publish_round_trips_event_as_json_in_data_field(redis_client: Redis) -> None:
    run_id = uuid.uuid4()
    sink = RedisEventSink(redis_client)
    event = _event(run_id, seq=1)

    sink.publish(event)

    stream = f"aether:runs:{run_id}:events"
    ((_, fields),) = _xrange_all(redis_client, stream)
    assert RunEvent.model_validate_json(fields["data"]) == event


def test_two_events_are_stored_in_seq_order(redis_client: Redis) -> None:
    run_id = uuid.uuid4()
    sink = RedisEventSink(redis_client)

    sink.publish(_event(run_id, seq=1))
    sink.publish(_event(run_id, seq=2))

    stream = f"aether:runs:{run_id}:events"
    entries = _xrange_all(redis_client, stream)
    assert [entry_id for entry_id, _ in entries] == ["1-0", "2-0"]


def test_republishing_the_same_seq_succeeds_without_growing_the_stream(
    redis_client: Redis,
) -> None:
    """spec 0002 2.7 개정 2, R-16: 재개가 종결 이벤트를 같은 `seq` 로 다시 발행해도
    `EventSink` 는 예외 없이 끝나고 스트림 길이는 그대로입니다."""
    run_id = uuid.uuid4()
    sink = RedisEventSink(redis_client)
    event = _event(run_id, seq=1)
    sink.publish(event)

    sink.publish(event)  # 재발행 — 예외를 내면 안 됩니다.

    stream = f"aether:runs:{run_id}:events"
    assert redis_client.xlen(stream) == 1


def test_other_response_errors_are_not_absorbed(redis_client: Redis) -> None:
    """같은 seq 재발행 흡수는 그 오류 문자열에만 한정됩니다 — 다른 `ResponseError`
    (예: 스트림 자리에 이미 문자열 키가 있음)는 그대로 올라옵니다."""
    run_id = uuid.uuid4()
    stream = f"aether:runs:{run_id}:events"
    redis_client.set(stream, "not-a-stream")
    sink = RedisEventSink(redis_client)

    with pytest.raises(ResponseError):
        sink.publish(_event(run_id, seq=1))


def test_run_finished_sets_ttl_on_the_stream(redis_client: Redis) -> None:
    run_id = uuid.uuid4()
    sink = RedisEventSink(redis_client, ttl_seconds=86400)

    sink.publish(_event(run_id, seq=1, event_type="run.finished"))

    stream = f"aether:runs:{run_id}:events"
    ttl = redis_client.ttl(stream)
    assert 0 < ttl <= 86400


def test_non_finished_events_do_not_set_ttl(redis_client: Redis) -> None:
    run_id = uuid.uuid4()
    sink = RedisEventSink(redis_client, ttl_seconds=86400)

    sink.publish(_event(run_id, seq=1, event_type="run.status"))

    stream = f"aether:runs:{run_id}:events"
    assert redis_client.ttl(stream) == -1  # TTL 없음(영속)


def test_maxlen_trims_older_entries(redis_client: Redis) -> None:
    """`MAXLEN ~ maxlen` 은 근사 트리밍입니다 — 매 XADD 마다 완전히 채워진 노드를
    지우므로, 노드 크기를 1 로 낮춰(`stream-node-max-entries`) 결정적으로 재현합니다."""
    run_id = uuid.uuid4()
    redis_client.config_set("stream-node-max-entries", 1)
    try:
        sink = RedisEventSink(redis_client, maxlen=2)
        for seq in range(1, 6):
            sink.publish(_event(run_id, seq=seq))

        stream = f"aether:runs:{run_id}:events"
        entries = _xrange_all(redis_client, stream)
        ids = [entry_id for entry_id, _ in entries]
        assert "1-0" not in ids
        assert len(ids) <= 3
    finally:
        redis_client.config_set("stream-node-max-entries", 100)


def _status_message(
    *,
    status: RunStatus = RunStatus.RUNNING,
    started_at: datetime | None = None,
    finished_at: datetime | None = None,
    failure_reason: FailureReason | None = None,
    trace_id: str | None = None,
) -> StatusMessage:
    return StatusMessage(
        run_id=uuid.uuid4(),
        seq=1,
        status=status,
        at=datetime(2026, 1, 1, tzinfo=UTC),
        started_at=started_at,
        finished_at=finished_at,
        failure_reason=failure_reason,
        trace_id=trace_id,
    )


def test_notify_writes_required_fields_as_strings(redis_client: Redis) -> None:
    notifier = RedisStatusNotifier(redis_client)
    message = _status_message()

    notifier.notify(message)

    ((_, fields),) = _xrange_all(redis_client, "aether:runs:status")
    assert fields["run_id"] == str(message.run_id)
    assert fields["seq"] == "1"
    assert fields["status"] == "running"
    assert fields["at"] == message.at.isoformat()


def test_notify_omits_absent_optional_fields(redis_client: Redis) -> None:
    notifier = RedisStatusNotifier(redis_client)
    message = _status_message()

    notifier.notify(message)

    ((_, fields),) = _xrange_all(redis_client, "aether:runs:status")
    assert "started_at" not in fields
    assert "finished_at" not in fields
    assert "failure_reason" not in fields
    assert "trace_id" not in fields


def test_notify_includes_optional_fields_when_present(redis_client: Redis) -> None:
    notifier = RedisStatusNotifier(redis_client)
    message = _status_message(
        status=RunStatus.FAILED,
        started_at=datetime(2026, 1, 1, tzinfo=UTC),
        finished_at=datetime(2026, 1, 1, 0, 5, tzinfo=UTC),
        failure_reason=FailureReason.MODEL_ERROR,
        trace_id="trace-abc",
    )

    notifier.notify(message)

    ((_, fields),) = _xrange_all(redis_client, "aether:runs:status")
    assert message.started_at is not None
    assert message.finished_at is not None
    assert fields["started_at"] == message.started_at.isoformat()
    assert fields["finished_at"] == message.finished_at.isoformat()
    assert fields["failure_reason"] == "model_error"
    assert fields["trace_id"] == "trace-abc"
