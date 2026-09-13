"""조립 지점: 유스케이스에 outbound 어댑터를 꽂고 inbound 어댑터에 포트 타입으로 건넵니다.

양쪽(inbound·outbound)을 다 아는 유일한 파일입니다(AR-10). 어댑터가 이 모듈을 import 하면
순환이 생기므로, CLI 실행 진입점은 여기의 `cli()` 이고 `adapters/inbound/cli.py` 는 함수만
가집니다(리뷰 F-6). 유스케이스(`application.usecases`) import 는 이 파일에만 있습니다.
"""

from __future__ import annotations

import psycopg
from fastapi import FastAPI

from aether_api.adapters.inbound.cli import build_parser
from aether_api.adapters.inbound.cli import keys_create as write_keys_create
from aether_api.adapters.inbound.cli import openapi as write_openapi
from aether_api.adapters.inbound.http.agents import build_agents_router
from aether_api.adapters.inbound.http.auth import require_principal
from aether_api.adapters.inbound.http.healthz import build_router
from aether_api.adapters.outbound.db.agent_repository import PostgresAgentRepository
from aether_api.adapters.outbound.db.api_keys import PostgresApiKeyStore
from aether_api.adapters.outbound.telemetry import init_telemetry
from aether_api.application.ports.inbound.authenticate import Authenticate
from aether_api.application.usecases.authenticate import AuthenticateUseCase
from aether_api.application.usecases.create_agent import CreateAgentUseCase
from aether_api.application.usecases.get_agent import GetAgentUseCase
from aether_api.application.usecases.get_agent_version import GetAgentVersionUseCase
from aether_api.application.usecases.issue_api_key import IssueApiKeyUseCase
from aether_api.application.usecases.list_agents import ListAgentsUseCase
from aether_api.application.usecases.update_agent import UpdateAgentUseCase
from aether_api.settings import Settings


def _postgres_api_key_store(settings: Settings) -> PostgresApiKeyStore:
    """호출될 때마다 새 연결을 여는 팩토리를 건넵니다 — 여기서는 연결을 열지 않습니다(H-3)."""
    return PostgresApiKeyStore(lambda: psycopg.connect(settings.psycopg_dsn))


def _postgres_agent_repository(settings: Settings) -> PostgresAgentRepository:
    """호출될 때마다 새 연결을 여는 팩토리를 건넵니다 — 여기서는 연결을 열지 않습니다(H-3)."""
    return PostgresAgentRepository(lambda: psycopg.connect(settings.psycopg_dsn))


def create_app(settings: Settings, *, authenticate: Authenticate | None = None) -> FastAPI:
    """설정을 읽어 telemetry 를 초기화하고 라우터를 등록한 `FastAPI` 앱을 조립합니다.

    `authenticate` 를 생략하면 PostgreSQL 어댑터로 지연 조립해 `app.state.authenticate`
    에 둡니다. 조립 시점에는 연결을 열지 않습니다 — 이 함수는 모듈 import 시(아래 `app`)
    실행되므로, DB 가 없는 단위 테스트와 `aether-api openapi` 가 이 경로를 그대로
    지나갑니다. 보호 경로는 Phase 1 의 라우터부터 `require_principal(app.state.authenticate)`
    를 의존성으로 받습니다 — P0-9 에는 보호할 제품 경로가 없습니다.
    """
    init_telemetry("api")

    if authenticate is None:
        authenticate = AuthenticateUseCase(_postgres_api_key_store(settings))

    app = FastAPI(title="aether-api", version=settings.version)
    app.state.authenticate = authenticate
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
    return app


app = create_app(Settings())
"""uvicorn 진입점: `uvicorn aether_api.main:app`."""


def cli() -> None:
    """`aether-api` 스크립트 진입점: 조립된 `app`/유스케이스를 `cli.py` 의 함수에 건넵니다.

    `openapi` 는 모듈 임포트 시 이미 조립된 `app`(위)을 재사용합니다 — 다시 조립하면
    telemetry 가 두 번 초기화됩니다. `keys create` 는 매번 새 `Settings()` 를 읽어
    `IssueApiKeyUseCase` 를 조립합니다 — CLI 프로세스는 매번 새로 뜨기 때문입니다.
    """
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "openapi":
        write_openapi(app)
    elif args.command == "keys" and args.keys_command == "create":
        settings = Settings()
        issue = IssueApiKeyUseCase(_postgres_api_key_store(settings))
        write_keys_create(issue, args.label)
