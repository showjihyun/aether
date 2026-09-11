"""spec 0001 R-9 · 2.9 (H-3 설계 검토): `Authenticate` 포트를 FastAPI 의존성으로 잇는 어댑터.

`application.ports.inbound.authenticate.Authenticate` **포트 타입**만 import 합니다
(AR-12) — 유스케이스 구현은 모릅니다. 실패는 WARNING 로그에 사유만 남기고(키 원문·
조각은 어디에도 남기지 않습니다), 응답은 고정 본문 401 + `WWW-Authenticate: Bearer`
입니다. `Authorization` 헤더의 스킴 비교는 대소문자를 가리지 않습니다(RFC 7235).
"""

from __future__ import annotations

import logging
from collections.abc import Callable

from fastapi import HTTPException, Request

from aether_api.application.ports.inbound.authenticate import Authenticate
from aether_api.domain.api_key import Principal, Unauthenticated

logger = logging.getLogger(__name__)

_BEARER_SCHEME = "bearer"


def _extract_bearer_token(authorization: str | None) -> str | None:
    """`Authorization: <scheme> <token>` 에서 스킴이 `bearer`(대소문자 무시)면 토큰만."""
    if authorization is None:
        return None
    parts = authorization.split(" ", 1)
    if len(parts) != 2:
        return None
    scheme, token = parts
    if scheme.lower() != _BEARER_SCHEME:
        return None
    return token


def require_principal(authenticate: Authenticate) -> Callable[[Request], Principal]:
    """`Authenticate` 포트를 FastAPI `Depends` 로 쓸 콜러블로 만듭니다."""

    def _dependency(request: Request) -> Principal:
        raw_key = _extract_bearer_token(request.headers.get("Authorization"))
        try:
            return authenticate(raw_key)
        except Unauthenticated as exc:
            logger.warning("authentication failed: %s", exc)
            raise HTTPException(
                status_code=401,
                detail="unauthorized",
                headers={"WWW-Authenticate": "Bearer"},
            ) from None

    return _dependency
