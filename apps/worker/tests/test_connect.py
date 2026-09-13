"""`serve()` 통합 테스트 — 실제 Redis(testcontainers). spec 0002 2.4, 2.14, R-13 (P1-5a).

`handler` 를 주입해 PostgreSQL·모델 게이트웨이 없이 소비 경로만 검증합니다 —
ready 로그 → consumer group 생성 → 메시지가 handler 에 도달 → `ack=True` 면 pending
0 → heartbeat 키 존재 → `stop` 뒤 5초 안에 종료. 프로덕션 조립(PostgreSQL·model
gateway·Redis 이벤트/상태 어댑터)이 실제로 맞물리는지는 `main.py` 단위 테스트가
아니라 compose 의 수동 확인(plan 0002 P1-5a 순서 5)이 담당합니다 — 여기서
PostgreSQL 컨테이너까지 띄우면 이 파일의 책임(연결·소비·heartbeat)을 넘어섭니다.
"""

from __future__ import annotations

import threading
from uuid import uuid4

import pytest
from aether_worker.application.ports.inbound.handle_run_requested import (
    HandleOutcome,
    RequestedMessage,
)
from aether_worker.main import serve
from aether_worker.settings import Settings
from redis import Redis

from tests.support.waiting import wait_until

pytestmark = pytest.mark.integration

_STOP_JOIN_TIMEOUT = 5.0


def _settings_for(redis_url: str) -> Settings:
    return Settings(
        redis_url=redis_url,
        worker_connect_max_attempts=5,
        worker_connect_base_delay=0.1,
        worker_connect_max_delay=0.5,
        worker_consumer=f"test-consumer-{uuid4()}",
        worker_heartbeat_seconds=1,
    )


class _NeverCalledHandler:
    """이 테스트가 메시지를 보내지 않으므로 호출되면 안 됩니다."""

    def __call__(self, message: RequestedMessage) -> HandleOutcome:
        raise AssertionError(f"handler should not be called, got {message}")


def test_serve_becomes_ready_creates_the_group_and_beats_the_heartbeat(
    redis_url: str,
) -> None:
    """준비 완료는 `on_ready` 콜백이 건 `threading.Event` 로 직접 기다립니다(경합 없음)."""
    settings = _settings_for(redis_url)
    stop = threading.Event()
    ready = threading.Event()
    outcome: dict[str, int] = {}

    def _run() -> None:
        outcome["code"] = serve(
            settings, stop=stop, on_ready=ready.set, handler=_NeverCalledHandler()
        )

    thread = threading.Thread(target=_run, name="aether-worker-test")
    thread.start()
    try:
        became_ready = ready.wait(timeout=10.0)
        assert became_ready, "ready 콜백이 10초 안에 불리지 않았습니다"

        probe: Redis = Redis.from_url(settings.redis_url, decode_responses=True)
        groups = probe.xinfo_groups(settings.worker_stream)
        assert any(g["name"] == settings.worker_group for g in groups)

        heartbeat_key = f"aether:worker:{settings.worker_consumer}:heartbeat"
        beat_seen = wait_until(lambda: probe.exists(heartbeat_key) == 1, timeout=5.0)
        assert beat_seen, "heartbeat 키가 5초 안에 나타나지 않았습니다(spec 2.14, R-13)"
    finally:
        stop.set()
        thread.join(_STOP_JOIN_TIMEOUT)

    assert not thread.is_alive(), "stop 이벤트 뒤 5초 안에 스레드가 끝나지 않았습니다"
    assert outcome["code"] == 0


def test_serve_delivers_a_message_to_the_handler_and_acks_on_success(
    redis_url: str,
) -> None:
    settings = _settings_for(redis_url)
    stop = threading.Event()
    ready = threading.Event()
    received: list[RequestedMessage] = []

    def handler(message: RequestedMessage) -> HandleOutcome:
        received.append(message)
        stop.set()
        return HandleOutcome(ack=True, status=None)

    thread = threading.Thread(
        target=lambda: serve(settings, stop=stop, on_ready=ready.set, handler=handler),
        name="aether-worker-test",
    )
    thread.start()
    try:
        assert ready.wait(timeout=10.0), "ready 콜백이 10초 안에 불리지 않았습니다"

        probe: Redis = Redis.from_url(settings.redis_url, decode_responses=True)
        run_id = uuid4()
        agent_version_id = uuid4()
        probe.xadd(
            settings.worker_stream,
            {"run_id": str(run_id), "agent_version_id": str(agent_version_id)},
        )

        delivered = wait_until(lambda: len(received) == 1, timeout=5.0)
        assert delivered, "메시지가 5초 안에 handler 에 도달하지 않았습니다"
        assert received[0].run_id == run_id
        assert received[0].agent_version_id == agent_version_id

        acked = wait_until(
            lambda: probe.xpending(settings.worker_stream, settings.worker_group)["pending"] == 0,
            timeout=5.0,
        )
        assert acked, "handler 가 ack=True 를 돌려줬는데도 pending 이 남았습니다"
    finally:
        stop.set()
        thread.join(_STOP_JOIN_TIMEOUT)

    assert not thread.is_alive(), "stop 이벤트 뒤 5초 안에 스레드가 끝나지 않았습니다"
