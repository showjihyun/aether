"""`serve()` 통합 테스트 — 실제 Redis(testcontainers). Docker 가 필요합니다.

spec 2.3·2.6 의 Phase 0 계약을 검증합니다: (a) Redis 가 있으면 `ready` 로그 후
consumer group 이 실재, (b) `stop` 이 set 되면 5초 안에 스레드가 끝나고 반환값 0,
(c) 스트림에 메시지가 와도 처리하지 않고 ack 하지 않습니다.

(c) 에 대한 참고: `XREADGROUP` 으로 읽힌 메시지는 (NOACK 를 쓰지 않는 한) ack 여부와
무관하게 consumer group 의 pending entries list(PEL) 에 들어갑니다 — 이것이 Redis
Streams 가 List 와 달리 at-least-once 를 보장하는 방법입니다(spec 2.3). 그래서
"ack 하지 않았다" 의 관측 가능한 증거는 pending 이 **0 이 아니라 1** 로 남는
것입니다: 메시지가 소비는 됐지만(로그) 아직 확인응답되지 않았다는 뜻입니다.
"""

from __future__ import annotations

import threading
from collections.abc import Iterator

import pytest
from aether_worker.main import serve
from aether_worker.settings import Settings
from redis import Redis
from testcontainers.community.redis import RedisContainer

from tests.support.waiting import wait_until

pytestmark = pytest.mark.integration

_STOP_JOIN_TIMEOUT = 5.0


@pytest.fixture
def redis_container() -> Iterator[RedisContainer]:
    with RedisContainer("redis:7-alpine") as container:
        yield container


def _settings_for(container: RedisContainer) -> Settings:
    host = container.get_container_host_ip()
    port = container.get_exposed_port(6379)
    return Settings(
        redis_url=f"redis://{host}:{port}/0",
        worker_connect_max_attempts=5,
        worker_connect_base_delay=0.1,
        worker_connect_max_delay=0.5,
    )


def test_serve_becomes_ready_and_creates_the_consumer_group(
    redis_container: RedisContainer,
) -> None:
    """준비 완료는 `on_ready` 콜백이 건 `threading.Event` 로 직접 기다립니다.

    이전에는 `caplog.text` 에 "worker.ready" 가 나타날 때까지 고정 5초를 폴링했는데,
    integration 스위트 전체를 돌리면(다른 컨테이너들과 자원을 다투며) `serve()` 가
    5초 안에 그 지점에 도달하지 못해 재현성 있게 실패했습니다(단독 실행은 통과) —
    캡처된 stdout 에는 "ready" 출력이 있어 실제로는 준비가 됐지만 폴링 데드라인을
    넘긴 뒤였습니다. `on_ready` 콜백은 폴링이 아니라 준비된 순간 즉시 이벤트를
    set 하므로 이 경합이 없습니다.
    """
    settings = _settings_for(redis_container)
    stop = threading.Event()
    ready = threading.Event()
    outcome: dict[str, int] = {}

    def _run() -> None:
        outcome["code"] = serve(settings, stop=stop, on_ready=ready.set)

    thread = threading.Thread(target=_run, name="aether-worker-test")
    thread.start()
    try:
        became_ready = ready.wait(timeout=10.0)
        assert became_ready, "ready 콜백이 10초 안에 불리지 않았습니다"

        probe: Redis = Redis.from_url(settings.redis_url, decode_responses=True)
        groups = probe.xinfo_groups(settings.worker_stream)
        assert any(g["name"] == settings.worker_group for g in groups)
    finally:
        stop.set()
        thread.join(_STOP_JOIN_TIMEOUT)

    assert not thread.is_alive(), "stop 이벤트 뒤 5초 안에 스레드가 끝나지 않았습니다"
    assert outcome["code"] == 0


def test_serve_consumes_but_does_not_ack_a_queued_message(
    redis_container: RedisContainer,
) -> None:
    settings = _settings_for(redis_container)
    stop = threading.Event()

    probe: Redis = Redis.from_url(settings.redis_url, decode_responses=True)

    thread = threading.Thread(
        target=lambda: serve(settings, stop=stop),
        name="aether-worker-test",
    )
    thread.start()
    try:
        group_ready = wait_until(
            lambda: bool(probe.exists(settings.worker_stream)), timeout=_STOP_JOIN_TIMEOUT
        )
        assert group_ready, "worker 가 5초 안에 스트림/group 을 만들지 않았습니다"

        probe.xadd(settings.worker_stream, {"run_id": "r1", "agent_version_id": "a1"})

        # block_ms=1000 짜리 XREADGROUP 이 최소 한 번은 이 메시지를 읽을 시간을 줍니다.
        delivered = wait_until(
            lambda: probe.xpending(settings.worker_stream, settings.worker_group)["pending"] > 0,
            timeout=3.0,
        )
        assert delivered, "메시지가 3초 안에 소비되지 않았습니다(pending 에 나타나지 않음)"
    finally:
        stop.set()
        thread.join(_STOP_JOIN_TIMEOUT)

    assert not thread.is_alive()

    summary = probe.xpending(settings.worker_stream, settings.worker_group)
    assert summary["pending"] == 1, "읽힌 메시지는 ack 되지 않아 pending 에 1건 남아야 합니다"
