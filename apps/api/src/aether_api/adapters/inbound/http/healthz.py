"""`GET /healthz` — 인증 없음. 프로세스 liveness 만 답합니다(DB·Redis 를 보지 않습니다).

상수를 답하는 유스케이스 없는 순수 inbound 어댑터입니다 — `application` 을 import 하지 않습니다.
`main` 을 import 하지 않습니다.
"""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel


class HealthzResponse(BaseModel):
    """spec 2.3 의 계약 그대로: `{status, service, version}`."""

    status: str
    service: str
    version: str


def build_router(version: str) -> APIRouter:
    """`version` 은 조립(main.py)이 설정에서 읽어 인자로 건넵니다."""
    router = APIRouter()

    @router.get("/healthz", response_model=HealthzResponse)
    def healthz() -> HealthzResponse:
        return HealthzResponse(status="ok", service="api", version=version)

    return router
