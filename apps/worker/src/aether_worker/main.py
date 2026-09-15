"""조립 지점: 설정 → telemetry → 연결(백오프) → (프로덕션 조립 또는 주입된 handler) →
heartbeat 스레드 → `RequestedConsumer.run_until`(spec 0002 2.1, 2.4, 2.14, AR-10).

`stop`·`make_client`·`sleep`·`handler` 를 인자로 받는 `serve()` 가 실제 동작이고,
`run()`/`main()` 은 그것을 실제 시그널·시계·Redis 로 감쌉니다 — 테스트가 컨테이너
없이(또는 Redis 만으로) `serve()` 를 부를 수 있게 하기 위해서입니다. `handler` 가
`None` 이면 `_build_production_handler` 가 runtime 의 `ExecuteRunUseCase` 를
PostgreSQL·Redis·model gateway 어댑터로 조립합니다 — 이 파일만이 `adapters.inbound`
와 `adapters.outbound` 를 함께 import 합니다(AR-10, `tests/arch/
test_composition_only_in_main.py`).
"""

from __future__ import annotations

import logging
import signal
import sys
import time
from collections.abc import Callable
from threading import Event, Thread
from types import FrameType
from typing import NoReturn

import psycopg
from aether_runtime.adapters.outbound.db.run_declaration_reader import (
    PostgresRunDeclarationReader,
)
from aether_runtime.adapters.outbound.db.run_state_store import PostgresRunStateStore
from aether_runtime.adapters.outbound.model_gateway.fake import FakeModelGateway
from aether_runtime.adapters.outbound.model_gateway.openai_compatible import (
    OpenAICompatibleGateway,
)
from aether_runtime.adapters.outbound.redis.event_sink import RedisEventSink
from aether_runtime.adapters.outbound.redis.status_notifier import RedisStatusNotifier
from aether_runtime.adapters.outbound.system_clock import SystemClock
from aether_runtime.adapters.outbound.telemetry.noop_tracer import NoopTracer
from aether_runtime.adapters.outbound.threaded_lease_keeper import ThreadedLeaseKeeper
from aether_runtime.adapters.outbound.tools.registry import InMemoryToolRegistry
from aether_runtime.application.ports.outbound.model_gateway import ModelGateway
from aether_runtime.application.usecases.execute_run import ExecuteRunUseCase
from redis import Redis

from aether_worker.adapters.inbound.stream.requested_consumer import (
    RequestedConsumer,
    ensure_group,
)
from aether_worker.adapters.outbound.noop_trace_context import NoopTraceContext
from aether_worker.adapters.outbound.redis.heartbeat import Heartbeat
from aether_worker.adapters.outbound.telemetry import init_telemetry
from aether_worker.application.ports.inbound.handle_run_requested import HandleRunRequested
from aether_worker.application.usecases.handle_run_requested import HandleRunRequestedUseCase
from aether_worker.domain.backoff import BackoffPolicy
from aether_worker.settings import Settings

logger = logging.getLogger(__name__)

_HEARTBEAT_TTL_FACTOR = 3
_STOP_JOIN_TIMEOUT = 5.0


class WorkerStartupError(RuntimeError):
    """Redis 연결에 최종 실패했을 때. 원인을 메시지에 포함합니다."""


def _make_redis_client(redis_url: str) -> Callable[[], Redis]:
    """`make_client` 팩토리: 부를 때마다 새로 연결을 시도하고 `PING` 으로 확인합니다.

    `redis.Redis.from_url` 자체는 지연 연결이라 생성만으로는 실패를 알 수 없으므로,
    `ping()` 으로 실제 연결을 확인합니다.
    """

    def factory() -> Redis:
        client: Redis = Redis.from_url(redis_url, decode_responses=True)
        client.ping()
        return client

    return factory


def connect_with_backoff[T](
    make_client: Callable[[], T],
    policy: BackoffPolicy,
    sleep: Callable[[float], None],
) -> T:
    """`make_client` 가 성공할 때까지 `policy` 를 따라 재시도합니다.

    최대 `policy.max_attempts` 번 시도합니다. 마지막 시도까지 전부 실패하면
    `WorkerStartupError` 를 냅니다. 시도 사이(마지막 제외)마다 `sleep` 을 부르므로,
    `sleep` 호출 횟수는 정확히 `max_attempts - 1` 입니다.
    """
    last_error: Exception | None = None

    for attempt in range(1, policy.max_attempts + 1):
        try:
            return make_client()
        except Exception as exc:  # noqa: BLE001 - 원인과 무관하게 재시도 대상입니다
            last_error = exc
            logger.warning(
                "worker.connect.failed",
                extra={"attempt": attempt, "max_attempts": policy.max_attempts, "error": str(exc)},
            )
            if policy.should_retry(attempt):
                sleep(policy.delay_for(attempt))

    raise WorkerStartupError(
        f"Redis 연결 실패: {policy.max_attempts}번 시도 후 포기 (마지막 원인: {last_error})"
    ) from last_error


def _build_model_gateway(settings: Settings) -> ModelGateway:
    if settings.model_adapter == "fake":
        return FakeModelGateway.echo()
    return OpenAICompatibleGateway(
        settings.model_base_url or "",
        settings.model_id,
        settings.model_api_key,
        settings.model_thinking,
    )


def _build_production_handler(settings: Settings, client: Redis) -> HandleRunRequested:
    """PostgreSQL·model gateway·Redis 이벤트/상태 어댑터로 `ExecuteRunUseCase` 를
    조립하고, `HandleRunRequestedUseCase` 로 감쌉니다(spec 0002 2.1)."""

    def connect() -> psycopg.Connection:
        return psycopg.connect(settings.psycopg_dsn)

    execute_run = ExecuteRunUseCase(
        PostgresRunStateStore(connect),
        PostgresRunDeclarationReader(connect),
        _build_model_gateway(settings),
        InMemoryToolRegistry(SystemClock()),
        RedisEventSink(
            client, maxlen=settings.events_maxlen, ttl_seconds=settings.events_ttl_seconds
        ),
        RedisStatusNotifier(client),
        NoopTracer(),
        SystemClock(),
        owner=settings.worker_consumer,
        lease_ttl_seconds=settings.worker_lease_seconds,
        observation_max_chars=settings.observation_max_chars,
        lease_keeper=ThreadedLeaseKeeper(PostgresRunStateStore(connect)),
    )
    return HandleRunRequestedUseCase(execute_run, NoopTraceContext())


def _heartbeat_loop(heartbeat: Heartbeat, interval_seconds: float, stop: Event) -> None:
    while not stop.is_set():
        heartbeat.beat()
        stop.wait(interval_seconds)


def serve(
    settings: Settings,
    *,
    stop: Event,
    make_client: Callable[[], Redis] | None = None,
    sleep: Callable[[float], None] = time.sleep,
    on_ready: Callable[[], None] | None = None,
    handler: HandleRunRequested | None = None,
) -> int:
    """연결(백오프) → consumer group → heartbeat 스레드 → 소비 대기.

    Redis 연결에 최종 실패하면 stderr 에 원인을 남기고 1 을 반환합니다. 연결되면
    `ready` 를 로그·stdout 에 남기고 `stop` 이 set 될 때까지 대기하다가 0 을
    반환합니다. `make_client`·`sleep`·`handler` 는 테스트가 주입합니다 — `handler` 가
    `None` 이면 PostgreSQL·model gateway 를 포함한 프로덕션 조립을 씁니다.

    `on_ready` 는 `ready` 로그 직후 호출됩니다 — 테스트가 로그 캡처의 타이밍(폴링·
    스레드 경합)에 기대지 않고 `threading.Event` 로 준비 완료를 직접 기다릴 수
    있게 하기 위해서입니다. 기본값 `None` 이면 아무 일도 하지 않습니다.
    """
    init_telemetry("worker")

    policy = BackoffPolicy(
        max_attempts=settings.worker_connect_max_attempts,
        base_delay=settings.worker_connect_base_delay,
        max_delay=settings.worker_connect_max_delay,
    )
    client_factory = make_client or _make_redis_client(settings.redis_url)

    try:
        client = connect_with_backoff(client_factory, policy, sleep)
    except WorkerStartupError as exc:
        logger.error("worker.startup.failed", extra={"error": str(exc)})
        print(f"aether-worker: {exc}", file=sys.stderr)
        return 1

    ensure_group(client, settings.worker_stream, settings.worker_group)

    active_handler = handler if handler is not None else _build_production_handler(settings, client)

    heartbeat = Heartbeat(
        client,
        f"aether:worker:{settings.worker_consumer}:heartbeat",
        settings.worker_heartbeat_seconds * _HEARTBEAT_TTL_FACTOR,
    )
    heartbeat_thread = Thread(
        target=_heartbeat_loop,
        args=(heartbeat, settings.worker_heartbeat_seconds, stop),
        name="aether-worker-heartbeat",
        daemon=True,
    )
    heartbeat_thread.start()

    logger.info(
        "worker.ready",
        extra={"stream": settings.worker_stream, "group": settings.worker_group},
    )
    print(f"aether-worker: ready (stream={settings.worker_stream}, group={settings.worker_group})")
    if on_ready is not None:
        on_ready()

    consumer = RequestedConsumer(
        client,
        stream=settings.worker_stream,
        group=settings.worker_group,
        consumer=settings.worker_consumer,
        handler=active_handler,
        xautoclaim_min_idle_ms=settings.worker_xautoclaim_min_idle_ms,
    )
    consumer.run_until(stop)
    heartbeat_thread.join(_STOP_JOIN_TIMEOUT)
    return 0


def _install_signal_handlers(stop: Event) -> None:
    """등록 가능한 시그널(SIGTERM·SIGINT)에 `stop.set()` 을 건다.

    Windows 에는 POSIX SIGTERM 전달이 없고, 일부 시그널은 메인 스레드가 아니면
    등록할 수 없습니다 — 그런 환경에서는 조용히 건너뜁니다. 실제 종료 판정은
    `threading.Event` 로 하므로 테스트는 시그널을 보내지 않고 이 이벤트를 직접
    set 해서 검증합니다.
    """

    def _handler(signum: int, frame: FrameType | None) -> None:
        logger.info("worker.signal.received", extra={"signum": signum})
        stop.set()

    for sig_name in ("SIGTERM", "SIGINT"):
        sig = getattr(signal, sig_name, None)
        if sig is None:
            continue
        try:
            signal.signal(sig, _handler)
        except (ValueError, OSError):
            # 메인 스레드가 아니거나 플랫폼이 지원하지 않는 경우입니다. 무시합니다.
            continue


def run(argv: list[str] | None = None) -> int:
    """`aether-worker` 스크립트의 실제 진입 로직. `main()` 이 `sys.exit` 로 감쌉니다."""
    del argv  # 서브커맨드가 없습니다.
    logging.basicConfig(level=logging.INFO)

    stop = Event()
    _install_signal_handlers(stop)
    settings = Settings()
    return serve(settings, stop=stop)


def main() -> NoReturn:
    """`[project.scripts] aether-worker` 진입점."""
    sys.exit(run())
