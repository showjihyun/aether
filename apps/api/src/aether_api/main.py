"""조립 지점: 유스케이스에 outbound 어댑터를 꽂고 inbound 어댑터에 포트 타입으로 건넵니다.

양쪽(inbound·outbound)을 다 아는 유일한 파일입니다(AR-10). 어댑터가 이 모듈을 import 하면
순환이 생기므로, CLI 실행 진입점은 여기의 `cli()` 이고 `adapters/inbound/cli.py` 는 함수만
가집니다(리뷰 F-6).
"""

from __future__ import annotations

from fastapi import FastAPI

from aether_api.adapters.inbound.cli import build_parser
from aether_api.adapters.inbound.cli import openapi as write_openapi
from aether_api.adapters.inbound.http.healthz import build_router
from aether_api.adapters.outbound.telemetry import init_telemetry
from aether_api.settings import Settings


def create_app(settings: Settings) -> FastAPI:
    """설정을 읽어 telemetry 를 초기화하고 라우터를 등록한 `FastAPI` 앱을 조립합니다."""
    init_telemetry("api")

    app = FastAPI(title="aether-api", version=settings.version)
    app.include_router(build_router(settings.version))
    return app


app = create_app(Settings())
"""uvicorn 진입점: `uvicorn aether_api.main:app`."""


def cli() -> None:
    """`aether-api` 스크립트 진입점: 조립된 `app` 을 `cli.py` 의 함수에 건넵니다.

    모듈 임포트 시 이미 조립된 `app`(위)을 재사용합니다 — 다시 조립하면 telemetry 가
    두 번 초기화됩니다.
    """
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "openapi":
        write_openapi(app)
