"""spec 0002 2.2 (D-9), 2.4, D-11, R-8, R-12: Run HTTP 계약과 라우터.

계약(OpenAPI)이 구현보다 먼저 커밋됩니다(DP-1) — `apps/api/src/aether_api/adapters/
inbound/http/agents.py` 가 P1-1 에서 세운 관례와 같습니다: 이 모듈이 처음 등장했을
때 `build_runs_router` 는 `principal_dep` 하나만 받았고 라우트 본문은 전부
`NotImplementedError` 였습니다(계약 먼저 단계, `main.py` 가 그 라우터를 등록해
`packages/sdk/openapi.json` 을 생성한 뒤 유스케이스가 채워졌습니다 — P1-5b G1 red
증거는 성립하지 않습니다: 이 단계는 red→green 대상이 아니라 계약 자체가 산출물입니다,
spec DP-1, plan 0002 P1-5b 순서 1). 요청·응답 모델과 오류 상태 코드는 그 시점부터
지금까지 바뀌지 않았습니다 — G4 가 바꾼 것은 `build_runs_router` 의 시그니처(유스케이스
3개를 받음)와 라우트 본문뿐입니다.

`status`·`failure_reason` 필드는 `aether_runtime.domain` 의 타입을 그대로 씁니다 —
api 는 `aether_runtime.domain` 만 import 할 수 있습니다(AR-7 확장).

전 경로가 `require_principal(app.state.authenticate)` 뒤에 있습니다(R-8). 오류 응답은
`{"detail": "<코드>"}` 이고, 422(요청 검증 실패)는 FastAPI 기본 형태(배열)를 그대로
둡니다(spec 2.2) — sdk 가 둘을 구분합니다.

`agents.py` 와 같은 이유로 `from __future__ import annotations` 을 쓰지 않습니다 —
아래 라우트들은 팩토리 인자로 받은 지역 변수(`principal_dep`, 유스케이스 포트)를
캡처한 `Annotated[Principal, Depends(...)]` 를 파라미터 타입으로 씁니다. 애노테이션이
지연 문자열이 되면(PEP 563) FastAPI 가 그 문자열을 함수의 모듈 전역에서만 `eval` 하므로
클로저 지역 변수를 찾지 못해 의존성이 조용히 무시되고 422 가 납니다
(improvement-log 2026-09-11-017).
"""

from collections.abc import Callable
from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from aether_runtime.domain.failure import FailureReason
from aether_runtime.domain.run import RunStatus
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel

from aether_api.application.ports.inbound.runs import CancelRun, GetRun, RequestRun
from aether_api.domain.agent import AgentNotFound, AgentVersionNotFound
from aether_api.domain.api_key import Principal
from aether_api.domain.run import RunNotFound

# --- 요청·응답 모델 (spec 2.2 표의 필드 그대로) --------------------------------


class RunRequest(BaseModel):
    """`POST /agents/{agent_id}/run` 의 요청 본문."""

    input: str
    agent_version: int | None = None


class RunAccepted(BaseModel):
    """`POST /agents/{agent_id}/run` 의 성공 응답(202) — Run 은 항상 `queued` 로 시작합니다."""

    run_id: UUID
    agent_id: UUID
    agent_version: int
    status: Literal["queued"] = "queued"
    requested_at: datetime
    requested_by: UUID


class RunDetailResponse(BaseModel):
    """`GET /runs/{run_id}` 의 성공 응답 — `control.runs` 투영만 읽습니다(spec 0001 D-11)."""

    run_id: UUID
    agent_id: UUID
    agent_version: int
    status: RunStatus
    requested_at: datetime
    requested_by: UUID
    started_at: datetime | None
    finished_at: datetime | None
    failure_reason: FailureReason | None
    trace_id: str | None
    cancel_requested_at: datetime | None


class CancelAccepted(BaseModel):
    """`POST /runs/{run_id}/cancel` 의 성공 응답(202) — 멱등(spec 2.2, D-11)."""

    run_id: UUID
    status: RunStatus
    cancel_requested_at: datetime


# --- 오류 --------------------------------------------------------------------


def _agent_not_found() -> HTTPException:
    return HTTPException(status_code=404, detail="agent_not_found")


def _agent_version_not_found() -> HTTPException:
    return HTTPException(status_code=404, detail="agent_version_not_found")


def _run_not_found() -> HTTPException:
    return HTTPException(status_code=404, detail="run_not_found")


# --- 라우터 -------------------------------------------------------------------


def build_runs_router(
    principal_dep: Callable[[Request], Principal],
    request_run: RequestRun,
    get_run: GetRun,
    cancel_run: CancelRun,
) -> APIRouter:
    """`run`/`runs/{id}`/`cancel` 3경로를 등록합니다. 전부 `principal_dep` 뒤에
    있습니다(R-8). 유스케이스는 inbound 포트 **타입**으로만 받습니다(AR-12) — 구현은
    조립(`main.py`)이 건네줍니다.
    """
    router = APIRouter()
    require_principal_dep = Annotated[Principal, Depends(principal_dep)]

    @router.post(
        "/agents/{agent_id}/run",
        response_model=RunAccepted,
        status_code=status.HTTP_202_ACCEPTED,
        responses={
            404: {"description": "agent_not_found | agent_version_not_found"},
        },
    )
    def run_agent_route(
        agent_id: UUID,
        body: RunRequest,
        principal: require_principal_dep,
    ) -> RunAccepted:
        try:
            view = request_run(agent_id, body.input, body.agent_version, principal.key_id)
        except AgentNotFound:
            raise _agent_not_found() from None
        except AgentVersionNotFound:
            raise _agent_version_not_found() from None
        return RunAccepted(
            run_id=view.run_id,
            agent_id=view.agent_id,
            agent_version=view.agent_version,
            requested_at=view.requested_at,
            requested_by=view.requested_by,
        )

    @router.get(
        "/runs/{run_id}",
        response_model=RunDetailResponse,
        responses={404: {"description": "run_not_found"}},
    )
    def get_run_route(
        run_id: UUID,
        principal: require_principal_dep,
    ) -> RunDetailResponse:
        try:
            view = get_run(run_id)
        except RunNotFound:
            raise _run_not_found() from None
        return RunDetailResponse(
            run_id=view.run_id,
            agent_id=view.agent_id,
            agent_version=view.agent_version,
            status=view.status,
            requested_at=view.requested_at,
            requested_by=view.requested_by,
            started_at=view.started_at,
            finished_at=view.finished_at,
            failure_reason=view.failure_reason,
            trace_id=view.trace_id,
            cancel_requested_at=view.cancel_requested_at,
        )

    @router.post(
        "/runs/{run_id}/cancel",
        response_model=CancelAccepted,
        status_code=status.HTTP_202_ACCEPTED,
        responses={404: {"description": "run_not_found"}},
    )
    def cancel_run_route(
        run_id: UUID,
        principal: require_principal_dep,
    ) -> CancelAccepted:
        try:
            view = cancel_run(run_id)
        except RunNotFound:
            raise _run_not_found() from None
        assert view.cancel_requested_at is not None
        return CancelAccepted(
            run_id=view.run_id,
            status=view.status,
            cancel_requested_at=view.cancel_requested_at,
        )

    return router
