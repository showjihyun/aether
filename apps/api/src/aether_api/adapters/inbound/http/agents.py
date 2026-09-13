"""spec 0002 2.2 (D-9), R-8, R-12: Agent Registry HTTP 계약과 라우터.

계약(OpenAPI)이 구현보다 먼저 커밋됩니다(DP-1) — 이 모듈이 처음 등장했을 때
`build_agents_router` 는 `principal_dep` 하나만 받았고 라우트 본문은 전부
`NotImplementedError` 였습니다(계약 먼저 단계, `main.py` 가 그 라우터를 등록해
`packages/sdk/openapi.json` 을 생성한 뒤 유스케이스가 채워졌습니다 — P1-1 red 증거
참고). 요청·응답 모델과 오류 상태 코드는 그 시점부터 지금까지 바뀌지 않았습니다.

`definition` 필드는 `aether_runtime.domain.agent.AgentDefinition` 을 그대로 씁니다 —
api 는 `aether_runtime.domain` 만 import 할 수 있고(AR-7 확장) 그 타입을 복제하지
않습니다.

전 경로가 `require_principal(app.state.authenticate)` 뒤에 있습니다(R-8). 오류 응답은
`{"detail": "<코드>"}` 이고, 422(요청 검증 실패)는 FastAPI 기본 형태(배열)를 그대로
둡니다(spec 2.2) — sdk 가 둘을 구분합니다.

모듈 수준 라우터 + `build_agents_router(...)` 팩토리로 만듭니다. 의도적으로
`from __future__ import annotations` 을 쓰지 않습니다 — 아래 라우트들은 팩토리
인자로 받은 지역 변수(`principal_dep`, 유스케이스 포트)를 캡처한
`Annotated[Principal, Depends(...)]` 를 파라미터 타입으로 씁니다. 애노테이션이
지연 문자열이 되면(PEP 563) FastAPI 가 그 문자열을 함수의 모듈 전역에서만 `eval` 하므로
클로저 지역 변수를 찾지 못해 의존성이 조용히 무시되고 422 가 납니다
(improvement-log 2026-09-11-017, `test_auth_http.py` 와 같은 이유).
"""

from collections.abc import Callable
from datetime import datetime
from typing import Annotated
from uuid import UUID

from aether_runtime.domain.agent import AgentDefinition
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel

from aether_api.application.ports.inbound.agents import (
    CreateAgent,
    GetAgent,
    GetAgentVersion,
    ListAgents,
    UpdateAgent,
)
from aether_api.domain.agent import (
    AgentDetail,
    AgentNameTaken,
    AgentNotFound,
    AgentVersionConflict,
    AgentVersionNotFound,
)
from aether_api.domain.api_key import Principal

# --- 요청·응답 모델 (spec 2.2 표의 필드 그대로) --------------------------------


class AgentResponse(BaseModel):
    """`POST /agents` 의 성공 응답."""

    id: UUID
    name: str
    current_version: int
    created_at: datetime
    updated_at: datetime


class AgentSummary(BaseModel):
    """`GET /agents` 의 `items[]` 원소 — `created_at` 은 없습니다(spec 2.2 표 그대로)."""

    id: UUID
    name: str
    current_version: int
    updated_at: datetime


class ListAgentsResponse(BaseModel):
    """`GET /agents` 의 성공 응답."""

    items: list[AgentSummary]
    next_cursor: str | None = None


class AgentVersionEntry(BaseModel):
    """`GET /agents/{id}` 의 `versions[]` 원소 — 버전 번호와 생성 시각만."""

    version: int
    created_at: datetime


class AgentDetailResponse(BaseModel):
    """`GET /agents/{id}` 와 `PUT /agents/{id}` 의 성공 응답(같은 모양, spec 2.2)."""

    id: UUID
    name: str
    current_version: int
    definition: AgentDefinition
    versions: list[AgentVersionEntry]
    created_at: datetime
    updated_at: datetime


class AgentVersionResponse(BaseModel):
    """`GET /agents/{id}/versions/{version}` 의 성공 응답."""

    agent_id: UUID
    version: int
    definition: AgentDefinition
    created_at: datetime


class CreateAgentRequest(BaseModel):
    """`POST /agents` 의 요청 본문."""

    name: str
    definition: AgentDefinition


class UpdateAgentRequest(BaseModel):
    """`PUT /agents/{id}` 의 요청 본문 — `definition` 만. `name` 은 Phase 1 불변(D-9)."""

    definition: AgentDefinition


# --- 도메인 → 응답 모델 ------------------------------------------------------


def _to_detail_response(detail: AgentDetail) -> AgentDetailResponse:
    return AgentDetailResponse(
        id=detail.agent.id,
        name=detail.agent.name,
        current_version=detail.agent.current_version,
        definition=detail.definition,
        versions=[
            AgentVersionEntry(version=v.version, created_at=v.created_at) for v in detail.versions
        ],
        created_at=detail.agent.created_at,
        updated_at=detail.agent.updated_at,
    )


def _agent_not_found() -> HTTPException:
    return HTTPException(status_code=404, detail="agent_not_found")


def _agent_version_not_found() -> HTTPException:
    return HTTPException(status_code=404, detail="agent_version_not_found")


def _agent_name_taken() -> HTTPException:
    return HTTPException(status_code=409, detail="agent_name_taken")


def _agent_version_conflict() -> HTTPException:
    return HTTPException(status_code=409, detail="agent_version_conflict")


# --- 라우터 ---------------------------------------------------------------


def build_agents_router(
    principal_dep: Callable[[Request], Principal],
    create_agent: CreateAgent,
    list_agents: ListAgents,
    get_agent: GetAgent,
    get_agent_version: GetAgentVersion,
    update_agent: UpdateAgent,
) -> APIRouter:
    """`agents` 5경로를 등록합니다. 전부 `principal_dep` 뒤에 있습니다(R-8).

    유스케이스는 inbound 포트 **타입**으로만 받습니다(AR-12) — 구현은 조립(`main.py`)
    이 건네줍니다.
    """
    router = APIRouter()
    require_principal_dep = Annotated[Principal, Depends(principal_dep)]

    @router.post(
        "/agents",
        response_model=AgentResponse,
        status_code=status.HTTP_201_CREATED,
        responses={409: {"description": "agent_name_taken"}},
    )
    def create_agent_route(
        body: CreateAgentRequest,
        principal: require_principal_dep,
    ) -> AgentResponse:
        try:
            agent = create_agent(body.name, body.definition)
        except AgentNameTaken:
            raise _agent_name_taken() from None
        return AgentResponse(
            id=agent.id,
            name=agent.name,
            current_version=agent.current_version,
            created_at=agent.created_at,
            updated_at=agent.updated_at,
        )

    @router.get("/agents", response_model=ListAgentsResponse)
    def list_agents_route(
        principal: require_principal_dep,
        limit: int = Query(default=50, ge=1, le=200),
        cursor: str | None = Query(default=None),
    ) -> ListAgentsResponse:
        page = list_agents(limit, cursor)
        return ListAgentsResponse(
            items=[
                AgentSummary(
                    id=agent.id,
                    name=agent.name,
                    current_version=agent.current_version,
                    updated_at=agent.updated_at,
                )
                for agent in page.items
            ],
            next_cursor=page.next_cursor,
        )

    @router.get(
        "/agents/{agent_id}",
        response_model=AgentDetailResponse,
        responses={404: {"description": "agent_not_found"}},
    )
    def get_agent_route(
        agent_id: UUID,
        principal: require_principal_dep,
    ) -> AgentDetailResponse:
        try:
            detail = get_agent(agent_id)
        except AgentNotFound:
            raise _agent_not_found() from None
        return _to_detail_response(detail)

    @router.get(
        "/agents/{agent_id}/versions/{version}",
        response_model=AgentVersionResponse,
        responses={404: {"description": "agent_not_found | agent_version_not_found"}},
    )
    def get_agent_version_route(
        agent_id: UUID,
        version: int,
        principal: require_principal_dep,
    ) -> AgentVersionResponse:
        try:
            agent_version = get_agent_version(agent_id, version)
        except AgentNotFound:
            raise _agent_not_found() from None
        except AgentVersionNotFound:
            raise _agent_version_not_found() from None
        return AgentVersionResponse(
            agent_id=agent_version.agent_id,
            version=agent_version.version,
            definition=agent_version.definition,
            created_at=agent_version.created_at,
        )

    @router.put(
        "/agents/{agent_id}",
        response_model=AgentDetailResponse,
        responses={
            404: {"description": "agent_not_found"},
            409: {"description": "agent_version_conflict"},
        },
    )
    def update_agent_route(
        agent_id: UUID,
        body: UpdateAgentRequest,
        principal: require_principal_dep,
    ) -> AgentDetailResponse:
        try:
            detail = update_agent(agent_id, body.definition)
        except AgentNotFound:
            raise _agent_not_found() from None
        except AgentVersionConflict:
            raise _agent_version_conflict() from None
        return _to_detail_response(detail)

    return router
