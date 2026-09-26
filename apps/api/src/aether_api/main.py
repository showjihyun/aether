"""조립 지점: 유스케이스에 outbound 어댑터를 꽂고 inbound 어댑터에 포트 타입으로 건넵니다.

양쪽(inbound·outbound)을 다 아는 유일한 파일입니다(AR-10). 어댑터가 이 모듈을 import 하면
순환이 생기므로, CLI 실행 진입점은 여기의 `cli()` 이고 `adapters/inbound/cli.py` 는 함수만
가집니다(리뷰 F-6). 유스케이스(`application.usecases`) import 는 이 파일에만 있습니다.

P1-5b 가 더한 것: `aether:runs:status` 투영 소비자를 FastAPI **lifespan** 에서 백그라운드
스레드로 돌립니다(spec 2.4, C-5) — api 가 Redis 를 처음 쓰는 자리라 연결이 지연되거나
실패해도 HTTP 는 그대로 뜹니다. `status_consumer` 를 주입할 수 있게 한 것은 테스트가
실제 연결 없이 lifespan 의 스레드 수명(시작·종료)만 검증할 수 있게 하기 위해서입니다.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from threading import Event, Thread

import psycopg
import redis.asyncio as aioredis
from fastapi import FastAPI
from redis import Redis

from aether_api.adapters.inbound.cli import agents_get_version as write_agents_get_version
from aether_api.adapters.inbound.cli import agents_list as write_agents_list
from aether_api.adapters.inbound.cli import build_parser
from aether_api.adapters.inbound.cli import events_schema as write_events_schema
from aether_api.adapters.inbound.cli import keys_create as write_keys_create
from aether_api.adapters.inbound.cli import openapi as write_openapi
from aether_api.adapters.inbound.cli import permissions_set as write_permissions_set
from aether_api.adapters.inbound.http.agents import build_agents_router
from aether_api.adapters.inbound.http.auth import require_principal
from aether_api.adapters.inbound.http.events import build_events_router
from aether_api.adapters.inbound.http.healthz import build_router
from aether_api.adapters.inbound.http.runs import build_runs_router
from aether_api.adapters.inbound.stream.status_consumer import StatusConsumer, ensure_group
from aether_api.adapters.outbound.db.agent_repository import PostgresAgentRepository
from aether_api.adapters.outbound.db.api_keys import PostgresApiKeyStore
from aether_api.adapters.outbound.db.run_declaration_store import PostgresRunDeclarationStore
from aether_api.adapters.outbound.db.tool_permissions import PostgresToolPermissionStore
from aether_api.adapters.outbound.otel_request_tracing import OtelRequestTracing
from aether_api.adapters.outbound.redis.run_event_reader import RedisRunEventReader
from aether_api.adapters.outbound.redis.run_notifier import RedisRunNotifier
from aether_api.adapters.outbound.telemetry import init_telemetry
from aether_api.application.ports.inbound.authenticate import Authenticate
from aether_api.application.ports.outbound.request_tracing import RequestTracing
from aether_api.application.usecases.apply_run_status import ApplyRunStatusUseCase
from aether_api.application.usecases.authenticate import AuthenticateUseCase
from aether_api.application.usecases.cancel_run import CancelRunUseCase
from aether_api.application.usecases.create_agent import CreateAgentUseCase
from aether_api.application.usecases.get_agent import GetAgentUseCase
from aether_api.application.usecases.get_agent_version import GetAgentVersionUseCase
from aether_api.application.usecases.get_run import GetRunUseCase
from aether_api.application.usecases.issue_api_key import IssueApiKeyUseCase
from aether_api.application.usecases.list_agents import ListAgentsUseCase
from aether_api.application.usecases.read_run_events import ReadRunEventsUseCase
from aether_api.application.usecases.request_run import RequestRunUseCase
from aether_api.application.usecases.run_exists import RunExistsUseCase
from aether_api.application.usecases.set_tool_permission import SetToolPermissionUseCase
from aether_api.application.usecases.update_agent import UpdateAgentUseCase
from aether_api.settings import Settings

logger = logging.getLogger(__name__)

_STATUS_STREAM = "aether:runs:status"
_STATUS_GROUP = "aether-api"
_STATUS_CONSUMER_CONNECT_MAX_ATTEMPTS = 10
_STATUS_CONSUMER_CONNECT_BASE_DELAY = 0.5
_STATUS_CONSUMER_CONNECT_MAX_DELAY = 8.0
_STATUS_CONSUMER_STOP_JOIN_TIMEOUT = 5.0


def _postgres_api_key_store(settings: Settings) -> PostgresApiKeyStore:
    """호출될 때마다 새 연결을 여는 팩토리를 건넵니다 — 여기서는 연결을 열지 않습니다(H-3)."""
    return PostgresApiKeyStore(lambda: psycopg.connect(settings.psycopg_dsn))


def _postgres_agent_repository(settings: Settings) -> PostgresAgentRepository:
    """호출될 때마다 새 연결을 여는 팩토리를 건넵니다 — 여기서는 연결을 열지 않습니다(H-3)."""
    return PostgresAgentRepository(lambda: psycopg.connect(settings.psycopg_dsn))


def _postgres_run_declaration_store(settings: Settings) -> PostgresRunDeclarationStore:
    """호출될 때마다 새 연결을 여는 팩토리를 건넵니다 — 여기서는 연결을 열지 않습니다(H-3)."""
    return PostgresRunDeclarationStore(lambda: psycopg.connect(settings.psycopg_dsn))


def _postgres_tool_permission_store(settings: Settings) -> PostgresToolPermissionStore:
    """호출될 때마다 새 연결을 여는 팩토리를 건넵니다 — 여기서는 연결을 열지 않습니다(H-3).

    🔒 spec 0003 D-14: 이 연결은 `aether_control` 역할로 접속해 정책 표를 씁니다.
    """
    return PostgresToolPermissionStore(lambda: psycopg.connect(settings.psycopg_dsn))


def _connect_redis_with_backoff(redis_url: str, stop: Event) -> Redis | None:
    """`stop` 이 set 되거나 시도를 다 쓸 때까지 지수 백오프로 Redis 연결을 시도합니다.

    연결에 최종 실패해도 `None` 을 돌려줄 뿐 예외를 내지 않습니다 — api 의 HTTP 는
    이미 떠 있고, 투영 소비자가 못 붙는 것은 로그로만 남깁니다(C-5).
    """
    delay = _STATUS_CONSUMER_CONNECT_BASE_DELAY
    for attempt in range(1, _STATUS_CONSUMER_CONNECT_MAX_ATTEMPTS + 1):
        if stop.is_set():
            return None
        try:
            client: Redis = Redis.from_url(redis_url, decode_responses=True)
            client.ping()
            return client
        except Exception as exc:  # noqa: BLE001 -- 연결 실패는 재시도 대상입니다(C-5)
            logger.warning(
                "api.status_consumer.connect_failed",
                extra={
                    "attempt": attempt,
                    "max_attempts": _STATUS_CONSUMER_CONNECT_MAX_ATTEMPTS,
                    "error": str(exc),
                },
            )
            if attempt < _STATUS_CONSUMER_CONNECT_MAX_ATTEMPTS:
                stop.wait(min(delay, _STATUS_CONSUMER_CONNECT_MAX_DELAY))
                delay = min(delay * 2, _STATUS_CONSUMER_CONNECT_MAX_DELAY)
    logger.error(
        "api.status_consumer.connect_exhausted",
        extra={"attempts": _STATUS_CONSUMER_CONNECT_MAX_ATTEMPTS},
    )
    return None


def _build_production_status_consumer(settings: Settings) -> Callable[[Event], None]:
    """lifespan 이 백그라운드 스레드에서 부를 함수 — 연결(백오프) → group → 소비 대기.

    연결에 최종 실패하면(또는 연결 시도 중 `stop` 이 set 되면) HTTP 는 그대로 두고
    아무 일도 하지 않습니다(C-5) — 그 증상은 `GET /runs/{id}` 가 낡은 투영을 답하는 것.
    """

    def run(stop: Event) -> None:
        client = _connect_redis_with_backoff(settings.redis_url, stop)
        if client is None or stop.is_set():
            return
        apply_status = ApplyRunStatusUseCase(_postgres_run_declaration_store(settings))
        ensure_group(client, _STATUS_STREAM, _STATUS_GROUP)
        consumer = StatusConsumer(client, apply_status, stream=_STATUS_STREAM, group=_STATUS_GROUP)
        consumer.run_until(stop)

    return run


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    """`aether:runs:status` 투영 소비자를 백그라운드 스레드로 돌립니다(spec 2.4, C-5).

    `create_app` 이 조립한(또는 테스트가 주입한) `app.state.status_consumer_runner` 를
    그대로 부릅니다. `aether-api openapi` 와 DB/Redis 없는 단위 테스트는
    `TestClient(app)` 를 `with` 없이 쓰므로 이 lifespan 자체가 돌지 않습니다.
    """
    stop = Event()
    runner: Callable[[Event], None] = app.state.status_consumer_runner
    thread = Thread(target=runner, args=(stop,), name="aether-api-status-consumer", daemon=True)
    thread.start()
    try:
        yield
    finally:
        stop.set()
        thread.join(_STATUS_CONSUMER_STOP_JOIN_TIMEOUT)


def create_app(
    settings: Settings,
    *,
    authenticate: Authenticate | None = None,
    status_consumer: Callable[[Event], None] | None = None,
    request_tracing: RequestTracing | None = None,
) -> FastAPI:
    """설정을 읽어 telemetry 를 초기화하고 라우터를 등록한 `FastAPI` 앱을 조립합니다.

    `authenticate` 를 생략하면 PostgreSQL 어댑터로 지연 조립해 `app.state.authenticate`
    에 둡니다. `status_consumer` 를 생략하면 Redis 로 지연 조립합니다 — 둘 다 조립
    시점에는 연결을 열지 않습니다. 이 함수는 모듈 import 시(아래 `app`) 실행되므로,
    DB/Redis 가 없는 단위 테스트와 `aether-api openapi` 가 이 경로를 그대로 지나갑니다.

    `request_tracing`(P1-8, spec 0002 2.9)을 생략하면 프로덕션 기본
    `OtelRequestTracing()`(전역 `TracerProvider`, `init_telemetry` 가 이미 등록해
    둔 것)을 씁니다 — `RequestRunUseCase` 가 이것으로 `run.request` span 을 엽니다.
    테스트는 독립된 `TracerProvider` 로 만든 `OtelRequestTracing(provider)` 를
    주입해 전역 provider 를 건드리지 않습니다.

    투영 소비자는 FastAPI **lifespan** 에서만 스레드로 실행됩니다 — `TestClient(app)`
    를 `with` 없이 쓰면(기존 단위 테스트 관례) lifespan 이 돌지 않으므로 DB/Redis 없는
    단위 테스트는 소비자를 시작하지 않습니다. 실제로 시작되는 곳은 uvicorn 서버 기동과
    `with TestClient(app) as client:` 뿐입니다(`aether-api openapi` 도 lifespan 을
    돌리지 않습니다 — 조립된 `app` 의 `openapi()` 만 부릅니다).
    """
    init_telemetry("api")

    if request_tracing is None:
        request_tracing = OtelRequestTracing()

    if authenticate is None:
        authenticate = AuthenticateUseCase(_postgres_api_key_store(settings))

    app = FastAPI(title="aether-api", version=settings.version, lifespan=_lifespan)
    app.state.authenticate = authenticate
    app.state.status_consumer_runner = (
        status_consumer
        if status_consumer is not None
        else _build_production_status_consumer(settings)
    )
    app.include_router(build_router(settings.version))

    agent_repository = _postgres_agent_repository(settings)
    app.include_router(
        build_agents_router(
            require_principal(authenticate),
            CreateAgentUseCase(agent_repository),
            ListAgentsUseCase(agent_repository),
            GetAgentUseCase(agent_repository),
            GetAgentVersionUseCase(agent_repository),
            UpdateAgentUseCase(agent_repository),
        )
    )

    run_declaration_store = _postgres_run_declaration_store(settings)
    run_notifier = RedisRunNotifier(Redis.from_url(settings.redis_url, decode_responses=True))
    app.include_router(
        build_runs_router(
            require_principal(authenticate),
            RequestRunUseCase(
                agent_repository, run_declaration_store, run_notifier, tracing=request_tracing
            ),
            GetRunUseCase(run_declaration_store),
            CancelRunUseCase(run_declaration_store),
        )
    )

    event_reader = RedisRunEventReader(
        # `socket_timeout=None`: `redis.asyncio.Redis` 의 기본값(5초)이 그대로면
        # `RedisRunEventReader.read` 의 블록 `XREAD`(기본 block_ms)와 거의 같은
        # 길이라 서버 쪽 BLOCK 응답보다 클라이언트 쪽 소켓 타임아웃이 먼저 발화해
        # `redis.exceptions.TimeoutError` 로 깨질 수 있습니다(실측, spec 0002 2.7).
        # 취소는 `asyncio.Task.cancel()` 이 즉시 처리하므로(확인함) 소켓 타임아웃
        # 자체가 취소 수단일 필요가 없습니다 — `BLOCK` 인자 하나로 상한을 둡니다.
        aioredis.Redis.from_url(settings.redis_url, decode_responses=True, socket_timeout=None)
    )
    app.include_router(
        build_events_router(
            require_principal(authenticate),
            ReadRunEventsUseCase(event_reader, run_declaration_store),
            RunExistsUseCase(run_declaration_store),
        )
    )
    return app


app = create_app(Settings())
"""uvicorn 진입점: `uvicorn aether_api.main:app`."""


def cli() -> None:
    """`aether-api` 스크립트 진입점: 조립된 `app`/유스케이스를 `cli.py` 의 함수에 건넵니다.

    `openapi` 는 모듈 임포트 시 이미 조립된 `app`(위)을 재사용합니다 — 다시 조립하면
    telemetry 가 두 번 초기화됩니다. `keys create`·`agents get-version`·`agents list` 는 매번 새
    `Settings()` 를 읽어 유스케이스를 조립합니다 — CLI 프로세스는 매번 새로 뜨기
    때문입니다.
    """
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "openapi":
        write_openapi(app)
    elif args.command == "events-schema":
        write_events_schema()
    elif args.command == "keys" and args.keys_command == "create":
        settings = Settings()
        issue = IssueApiKeyUseCase(_postgres_api_key_store(settings))
        write_keys_create(issue, args.label)
    elif args.command == "agents" and args.agents_command == "get-version":
        settings = Settings()
        get_agent_version = GetAgentVersionUseCase(_postgres_agent_repository(settings))
        write_agents_get_version(get_agent_version, args.agent_id, args.version)
    elif args.command == "agents" and args.agents_command == "list":
        settings = Settings()
        list_agents = ListAgentsUseCase(_postgres_agent_repository(settings))
        write_agents_list(list_agents, args.limit, args.cursor, args.name)
    elif args.command == "permissions" and args.permissions_command in ("allow", "deny"):
        settings = Settings()
        agent_repository = _postgres_agent_repository(settings)
        set_tool_permission = SetToolPermissionUseCase(
            GetAgentVersionUseCase(agent_repository), _postgres_tool_permission_store(settings)
        )
        write_permissions_set(
            set_tool_permission,
            args.agent_id,
            args.version,
            args.server,
            args.tool,
            args.permissions_command,
        )
