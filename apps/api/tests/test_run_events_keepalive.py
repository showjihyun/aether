"""spec 0002 2.7 확장: 중간 프록시가 idle 커넥션을 끊지 않도록, 다음 이벤트가
`_KEEPALIVE_SECONDS` 안에 오지 않으면 SSE 주석(`: keep-alive\\n\\n`)을 대신 냅니다.

`events._KEEPALIVE_SECONDS` 를 짧게 monkeypatch 해 실제로 15초를 기다리지 않고
`asyncio.Event` 로 이벤트 도착을 통제합니다(R-11) — `build_events_router` 가 만든
라우트를 `test_sse_route_is_async.py` 와 같은 방식으로 직접 호출합니다.
"""

import asyncio
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from aether_api.adapters.inbound.http import events as events_module
from aether_api.adapters.inbound.http.events import build_events_router
from aether_api.domain.api_key import Principal
from aether_runtime.domain.events import RunEvent
from fastapi.routing import APIRoute
from starlette.requests import Request

pytestmark = pytest.mark.anyio


def _principal_dep(request: Request) -> Principal:
    del request
    return Principal(key_id=uuid4(), label="test")


async def test_idle_stream_sends_keepalive_comment_between_events(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(events_module, "_KEEPALIVE_SECONDS", 0.05)
    target_run_id = uuid4()
    release = asyncio.Event()

    async def _fake_read_run_events(
        run_id: object, after_seq: int | None
    ) -> AsyncIterator[RunEvent]:
        del run_id, after_seq
        yield RunEvent(
            run_id=target_run_id,
            seq=1,
            at=datetime.now(UTC),
            type="run.status",
            payload={"status": "queued"},
        )
        await release.wait()
        yield RunEvent(
            run_id=target_run_id,
            seq=2,
            at=datetime.now(UTC),
            type="run.finished",
            payload={"status": "succeeded"},
        )

    router = build_events_router(_principal_dep, _fake_read_run_events, lambda run_id: True)
    (route,) = [r for r in router.routes if isinstance(r, APIRoute)]
    principal = Principal(key_id=uuid4(), label="test")

    response = await route.endpoint(run_id=target_run_id, principal=principal, last_event_id=None)
    body = response.body_iterator

    first_chunk = await asyncio.wait_for(body.__anext__(), timeout=2.0)
    assert first_chunk.startswith("id: 1\nevent: run.status\n")

    keepalive_chunk = await asyncio.wait_for(body.__anext__(), timeout=2.0)
    assert keepalive_chunk == ": keep-alive\n\n"

    release.set()
    second_chunk = await asyncio.wait_for(body.__anext__(), timeout=2.0)
    assert second_chunk.startswith("id: 2\nevent: run.finished\n")
