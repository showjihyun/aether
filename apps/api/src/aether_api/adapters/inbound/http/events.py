"""spec 0002 2.2, 2.7, D-4, R-8, R-12: Run 이벤트 SSE HTTP 계약과 라우터.

계약(OpenAPI)이 구현보다 먼저 커밋됩니다(DP-1) — `agents.py`·`runs.py` 가 세운
관례와 같습니다: 이 모듈이 처음 등장했을 때(G1) 라우트 본문은 `NotImplementedError`
였고, `main.py` 가 이 라우터를 등록해 `packages/sdk/openapi.json` 을 생성한 뒤
유스케이스가 채워졌습니다(G3) — G1 red 증거는 성립하지 않습니다: 그 단계는
red→green 대상이 아니라 계약 자체가 산출물입니다(spec DP-1).

`GET /runs/{run_id}/events` 는 `text/event-stream` 을 냅니다 — `response_model` 을
두지 않고 반환 타입을 `StreamingResponse` 로 선언해 FastAPI 가 그 값을 그대로
돌려주게 하고, `responses=` 로 실제 매체 유형과 오류 상태 코드를 OpenAPI 에 직접
적습니다(2.7).

**404 를 스트리밍 시작 전에 판정**합니다: `read_run_events(...)` 가 돌려주는 비동기
제너레이터의 **첫 이벤트를 미리 당겨**(`__anext__()`) `RunNotFound` 를 여기서
잡습니다 — `StreamingResponse` 가 한 번 시작되면(첫 바이트가 나가면) 상태 코드를
더 이상 바꿀 수 없기 때문입니다. 그 뒤의 본 스트리밍 제너레이터는 이미 당겨 둔 첫
이벤트부터 이어 보냅니다.

**클라이언트 단절**은 `asyncio.CancelledError` 로 옵니다(Starlette 의
`StreamingResponse` 가 단절을 감지하면 스트리밍 태스크를 취소합니다) — 조용히
끝냅니다(2.7 "종료"): worker 는 이 취소를 모르고 Run 을 계속 실행합니다(AR-7, R-3).

`agents.py`·`runs.py` 와 같은 이유로 `from __future__ import annotations` 을 쓰지
않습니다 — 아래 라우트는 팩토리 인자로 받은 지역 변수(`principal_dep`)를 캡처한
`Annotated[Principal, Depends(...)]` 를 파라미터 타입으로 씁니다. 애노테이션이 지연
문자열이 되면(PEP 563) FastAPI 가 그 문자열을 함수의 모듈 전역에서만 `eval` 하므로
클로저 지역 변수를 찾지 못해 의존성이 조용히 무시되고 422 가 납니다
(improvement-log 2026-09-11-017).
"""

import asyncio
import logging
from collections.abc import AsyncIterator, Callable
from typing import Annotated
from uuid import UUID

from aether_runtime.domain.events import RunEvent
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import StreamingResponse

from aether_api.application.ports.inbound.read_run_events import ReadRunEvents
from aether_api.domain.api_key import Principal
from aether_api.domain.run import RunNotFound

logger = logging.getLogger(__name__)


def _run_not_found() -> HTTPException:
    return HTTPException(status_code=404, detail="run_not_found")


def _format_sse(event: RunEvent) -> str:
    """`id: <seq>\\nevent: <type>\\ndata: <봉투 JSON>\\n\\n`(spec 2.7 "SSE 필드").

    `RunEvent.model_dump_json()` 은 압축된 한 줄 JSON 을 냅니다 — `data:` 는 한
    줄이면 됩니다(봉투 자체가 개행을 담지 않으므로 멀티라인 조립이 필요 없습니다).
    """
    return f"id: {event.seq}\nevent: {event.type}\ndata: {event.model_dump_json()}\n\n"


def build_events_router(
    principal_dep: Callable[[Request], Principal],
    read_run_events: ReadRunEvents,
) -> APIRouter:
    """`GET /runs/{run_id}/events` 하나를 등록합니다. `principal_dep` 뒤에
    있습니다(R-8). 유스케이스는 inbound 포트 **타입**으로만 받습니다(AR-12) —
    구현은 조립(`main.py`)이 건네줍니다.
    """
    router = APIRouter()
    require_principal_dep = Annotated[Principal, Depends(principal_dep)]

    @router.get(
        "/runs/{run_id}/events",
        response_class=StreamingResponse,
        responses={
            200: {"content": {"text/event-stream": {}}, "description": "Run 이벤트 SSE 스트림"},
            401: {"description": "unauthorized"},
            404: {"description": "run_not_found"},
        },
    )
    async def get_run_events_route(
        run_id: UUID,
        principal: require_principal_dep,
        last_event_id: Annotated[int | None, Header(alias="Last-Event-ID")] = None,
    ) -> StreamingResponse:
        del principal
        events = read_run_events(run_id, last_event_id)
        try:
            first_event: RunEvent | None = await events.__anext__()
        except RunNotFound:
            raise _run_not_found() from None
        except StopAsyncIteration:
            first_event = None

        async def _stream() -> AsyncIterator[str]:
            try:
                if first_event is not None:
                    yield _format_sse(first_event)
                async for event in events:
                    yield _format_sse(event)
            except asyncio.CancelledError:
                # 클라이언트 단절(2.7 "종료") — worker 는 이 취소를 모릅니다(AR-7, R-3).
                logger.info("api.run_events.client_disconnected", extra={"run_id": str(run_id)})
                return

        return StreamingResponse(_stream(), media_type="text/event-stream")

    return router
