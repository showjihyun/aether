"""spec 0002 2.7 확장(AD-2 결함 수정): 첫 이벤트가 오기 전에도 keep-alive 가
나가야 합니다.

기존 `events.py` 는 `StreamingResponse` 를 만들기 **전에** 첫 이벤트를
`__anext__()` 로 미리 당겼습니다(404 판정 목적) — 그래서 Run 이 아직 이벤트를 하나도
내지 않은 동안은 응답 헤더조차 나가지 않고 `_KEEPALIVE_SECONDS` 의 보호를 받지
못했습니다(evaluation/runs 네 번의 독립 보고). 이 결함 수정은 존재 확인을
`RunExists` 인바운드 포트로 분리하고, 첫 이벤트 대기도 `_stream()` 안의 keep-alive
루프를 타게 합니다.

`events._KEEPALIVE_SECONDS` 를 짧게 monkeypatch 해 실제로 15초를 기다리지 않습니다
(R-11). `build_events_router` 가 만든 라우트를 `test_sse_route_is_async.py` 와 같은
방식으로 직접 호출합니다.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from aether_api.adapters.inbound.http import events as events_module
from aether_api.adapters.inbound.http.events import build_events_router
from aether_api.application.ports.inbound.run_exists import RunExists
from aether_api.domain.api_key import Principal
from aether_api.domain.run import RunNotFound
from aether_runtime.domain.events import RunEvent
from fastapi import HTTPException
from fastapi.routing import APIRoute
from starlette.requests import Request

pytestmark = pytest.mark.anyio


def _principal_dep(request: Request) -> Principal:
    del request
    return Principal(key_id=uuid4(), label="test")


def _run_exists(exists: bool) -> RunExists:
    def _check(run_id: object) -> bool:
        del run_id
        return exists

    return _check


async def test_keepalive_is_sent_before_the_first_event_arrives(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """핵심 회귀 테스트: 첫 이벤트가 없어도 keep-alive 가 나갑니다."""
    monkeypatch.setattr(events_module, "_KEEPALIVE_SECONDS", 0.05)
    target_run_id = uuid4()
    release = asyncio.Event()

    async def _fake_read_run_events(
        run_id: object, after_seq: int | None
    ) -> AsyncIterator[RunEvent]:
        del run_id, after_seq
        await release.wait()
        yield RunEvent(
            run_id=target_run_id,
            seq=1,
            at=datetime.now(UTC),
            type="run.status",
            payload={"status": "queued"},
        )

    router = build_events_router(_principal_dep, _fake_read_run_events, _run_exists(True))
    (route,) = [r for r in router.routes if isinstance(r, APIRoute)]
    principal = Principal(key_id=uuid4(), label="test")

    response = await route.endpoint(run_id=target_run_id, principal=principal, last_event_id=None)
    body = response.body_iterator

    keepalive_chunk = await asyncio.wait_for(body.__anext__(), timeout=2.0)
    assert keepalive_chunk == ": keep-alive\n\n"

    release.set()
    first_chunk = await asyncio.wait_for(body.__anext__(), timeout=2.0)
    assert first_chunk.startswith("id: 1\nevent: run.status\n")


async def test_missing_run_still_returns_404_without_waiting_for_events() -> None:
    async def _fake_read_run_events(
        run_id: object, after_seq: int | None
    ) -> AsyncIterator[RunEvent]:
        del run_id, after_seq
        await asyncio.Event().wait()  # 절대 오지 않는 이벤트 — 호출되면 테스트가 걸립니다.
        return
        yield  # pragma: no cover -- 도달하지 않습니다. AsyncIterator 시그니처를 만족시킵니다.

    router = build_events_router(_principal_dep, _fake_read_run_events, _run_exists(False))
    (route,) = [r for r in router.routes if isinstance(r, APIRoute)]
    principal = Principal(key_id=uuid4(), label="test")

    with pytest.raises(HTTPException) as excinfo:
        await asyncio.wait_for(
            route.endpoint(run_id=uuid4(), principal=principal, last_event_id=None), timeout=2.0
        )
    assert excinfo.value.status_code == 404


async def test_run_not_found_mid_stream_after_existence_check_ends_quietly() -> None:
    """존재 확인 뒤(레이스로 삭제됨) 스트림 도중 `RunNotFound` 가 나면 이미 200 을
    보냈으므로 조용히 끝냅니다 — 예외 없이 스트림이 종료됩니다."""

    async def _fake_read_run_events(
        run_id: object, after_seq: int | None
    ) -> AsyncIterator[RunEvent]:
        del run_id, after_seq
        raise RunNotFound(uuid4())
        yield  # pragma: no cover

    router = build_events_router(_principal_dep, _fake_read_run_events, _run_exists(True))
    (route,) = [r for r in router.routes if isinstance(r, APIRoute)]
    principal = Principal(key_id=uuid4(), label="test")

    response = await route.endpoint(run_id=uuid4(), principal=principal, last_event_id=None)
    body = response.body_iterator

    with pytest.raises(StopAsyncIteration):
        await asyncio.wait_for(body.__anext__(), timeout=2.0)
