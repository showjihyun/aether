"""spec 0002 2.7, R-8: `GET /runs/{run_id}/events` 라우트는 비동기 제너레이터이고
`StreamingResponse` 를 돌려줍니다 — SSE 스트리밍은 동기 핸들러(스레드풀)에서 돌리면
클라이언트 단절을 취소로 옮길 수 없습니다(C-4, R-3).

`build_events_router` 가 만든 실제 `APIRoute.endpoint` 를 직접 불러(FastAPI 의
의존성 해석을 거치지 않고) 코루틴 함수인지·반환값이 `StreamingResponse` 인지
확인합니다.
"""

from __future__ import annotations

import inspect
from collections.abc import AsyncIterator
from uuid import uuid4

import pytest
from aether_api.adapters.inbound.http.events import build_events_router
from aether_api.domain.api_key import Principal
from aether_runtime.domain.events import RunEvent
from fastapi.responses import StreamingResponse
from fastapi.routing import APIRoute
from starlette.requests import Request

pytestmark = pytest.mark.anyio


async def _fake_read_run_events(run_id: object, after_seq: int | None) -> AsyncIterator[RunEvent]:
    del run_id, after_seq
    return
    yield  # pragma: no cover -- 도달하지 않습니다. AsyncIterator 시그니처를 만족시킵니다.


def _principal_dep(request: Request) -> Principal:
    del request
    return Principal(key_id=uuid4(), label="test")


def _events_route() -> APIRoute:
    router = build_events_router(_principal_dep, _fake_read_run_events)
    (route,) = [r for r in router.routes if isinstance(r, APIRoute)]
    return route


def test_events_route_endpoint_is_a_coroutine_function() -> None:
    route = _events_route()
    assert inspect.iscoroutinefunction(route.endpoint)


async def test_events_route_endpoint_returns_a_streaming_response() -> None:
    route = _events_route()
    principal = Principal(key_id=uuid4(), label="test")

    result = await route.endpoint(run_id=uuid4(), principal=principal, last_event_id=None)

    assert isinstance(result, StreamingResponse)
    assert result.media_type == "text/event-stream"
