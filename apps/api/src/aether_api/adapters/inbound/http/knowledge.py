"""spec 0004 2.4, D-4: Knowledge 적재 **선언** HTTP 계약과 라우터.

`runs.py` 와 같은 모양입니다 — api 는 `control.knowledge_sets`/`knowledge_ingestions`
의 선언만 하고(202), 실제 적재(청크·임베딩)는 worker 가 합니다. 전 경로가
`require_principal(app.state.authenticate)` 뒤에 있습니다(R-8 과 같은 경계). 오류
응답은 `{"detail": "<코드>"}`.

의도적으로 `from __future__ import annotations` 을 쓰지 않습니다 — `agents.py`/
`runs.py` 와 같은 이유(PEP 563 이 팩토리 지역 변수를 캡처한 `Annotated[...]` 의존성을
깨뜨립니다, improvement-log 2026-09-11-017).
"""

from collections.abc import Callable
from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel

from aether_api.application.ports.inbound.knowledge import (
    CreateKnowledgeSet,
    GetIngestion,
    RequestIngestion,
)
from aether_api.domain.api_key import Principal
from aether_api.domain.knowledge import (
    IngestionStatus,
    KnowledgeIngestionNotFound,
    KnowledgeSetNotFound,
)

# --- 요청·응답 모델 ------------------------------------------------------------


class CreateKnowledgeSetRequest(BaseModel):
    """`POST /knowledge-sets` 의 요청 본문."""

    name: str


class KnowledgeSetResponse(BaseModel):
    """`POST /knowledge-sets` 의 성공 응답."""

    id: UUID
    name: str
    created_at: datetime


class RequestIngestionRequest(BaseModel):
    """`POST /knowledge-sets/{id}/ingestions` 의 요청 본문 — `source` 는 Connector
    (Filesystem, spec D-6 과 같은 범위)가 읽을 위치."""

    source: str


class IngestionAccepted(BaseModel):
    """`POST /knowledge-sets/{id}/ingestions` 의 성공 응답(202) — 항상 `queued` 로
    시작합니다(`control.runs` 의 `RunAccepted` 와 같은 모양)."""

    ingestion_id: UUID
    knowledge_set_id: UUID
    source: str
    status: IngestionStatus
    requested_at: datetime


class IngestionDetailResponse(BaseModel):
    """`GET /knowledge-ingestions/{id}` 의 성공 응답 — 선언·투영만 읽습니다."""

    ingestion_id: UUID
    knowledge_set_id: UUID
    source: str
    status: IngestionStatus
    requested_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    failure_reason: str | None


# --- 오류 --------------------------------------------------------------------


def _knowledge_set_not_found() -> HTTPException:
    return HTTPException(status_code=404, detail="knowledge_set_not_found")


def _knowledge_ingestion_not_found() -> HTTPException:
    return HTTPException(status_code=404, detail="knowledge_ingestion_not_found")


# --- 라우터 -------------------------------------------------------------------


def build_knowledge_router(
    principal_dep: Callable[[Request], Principal],
    create_knowledge_set: CreateKnowledgeSet,
    request_ingestion: RequestIngestion,
    get_ingestion: GetIngestion,
) -> APIRouter:
    router = APIRouter()
    require_principal_dep = Annotated[Principal, Depends(principal_dep)]

    @router.post(
        "/knowledge-sets",
        response_model=KnowledgeSetResponse,
        status_code=status.HTTP_201_CREATED,
        responses={401: {"description": "unauthorized"}},
    )
    def create_knowledge_set_route(
        body: CreateKnowledgeSetRequest,
        principal: require_principal_dep,
    ) -> KnowledgeSetResponse:
        del principal
        view = create_knowledge_set(body.name)
        return KnowledgeSetResponse(id=view.id, name=view.name, created_at=view.created_at)

    @router.post(
        "/knowledge-sets/{knowledge_set_id}/ingestions",
        response_model=IngestionAccepted,
        status_code=status.HTTP_202_ACCEPTED,
        responses={
            401: {"description": "unauthorized"},
            404: {"description": "knowledge_set_not_found"},
        },
    )
    def request_ingestion_route(
        knowledge_set_id: UUID,
        body: RequestIngestionRequest,
        principal: require_principal_dep,
    ) -> IngestionAccepted:
        del principal
        try:
            view = request_ingestion(knowledge_set_id, body.source)
        except KnowledgeSetNotFound:
            raise _knowledge_set_not_found() from None
        return IngestionAccepted(
            ingestion_id=view.id,
            knowledge_set_id=view.knowledge_set_id,
            source=view.source,
            status=view.status,
            requested_at=view.requested_at,
        )

    @router.get(
        "/knowledge-ingestions/{ingestion_id}",
        response_model=IngestionDetailResponse,
        responses={
            401: {"description": "unauthorized"},
            404: {"description": "knowledge_ingestion_not_found"},
        },
    )
    def get_ingestion_route(
        ingestion_id: UUID,
        principal: require_principal_dep,
    ) -> IngestionDetailResponse:
        del principal
        try:
            view = get_ingestion(ingestion_id)
        except KnowledgeIngestionNotFound:
            raise _knowledge_ingestion_not_found() from None
        return IngestionDetailResponse(
            ingestion_id=view.id,
            knowledge_set_id=view.knowledge_set_id,
            source=view.source,
            status=view.status,
            requested_at=view.requested_at,
            started_at=view.started_at,
            finished_at=view.finished_at,
            failure_reason=view.failure_reason,
        )

    return router
