"""spec 0006 2.3 (D-3, D-11), R-4: 목록 경로 다섯의 HTTP 계약과 라우터.

`GET /agents` 의 페이지 규칙을 그대로 따릅니다 - `limit`(기본 50, 1~200)·`cursor`·
`{items, next_cursor}`. 새 규약(`page`·`offset`·`total`)을 만들지 않습니다. 필터는 상태 하나
(`status`)까지이고 상태가 없는 목록(workflows·knowledge-sets)에는 필터가 없습니다. 검색·정렬은
범위 밖입니다. 정렬은 고정입니다: 오래된 것부터 `(시각, id)` 오름차순 - `GET /agents` 와 같습니다.

경로는 **전부 additive** 입니다(D-11) - 기존 라우터(`agents.py`·`runs.py`·`workflows.py`·
`workflow_runs.py`·`knowledge.py`)와 그 응답 모델은 건드리지 않고 이 모듈이 따로 등록합니다.
Workflow Run 목록은 `control.workflow_runs` 투영만 읽습니다(노드 실행은 `data` 평면이라 범위
밖, D-4). 전 경로가 `principal_dep` 뒤에 있습니다(R-8).

의도적으로 `from __future__ import annotations` 을 쓰지 않습니다 - `agents.py` 와 같은 이유
(PEP 563 이 팩토리 지역 변수를 캡처한 `Annotated[...]` 의존성을 깨뜨립니다,
improvement-log 2026-09-11-017).
"""

from collections.abc import Callable
from datetime import datetime
from typing import Annotated
from uuid import UUID

from aether_runtime.domain.failure import FailureReason
from aether_runtime.domain.run import RunStatus
from aether_workflow.domain.run_status import WorkflowRunStatus
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel

from aether_api.application.ports.inbound.listings import (
    ListIngestions,
    ListKnowledgeSets,
    ListRuns,
    ListWorkflowRuns,
    ListWorkflows,
)
from aether_api.domain.api_key import Principal
from aether_api.domain.cursor import InvalidCursor
from aether_api.domain.knowledge import IngestionStatus, KnowledgeSetNotFound

# --- 응답 모델 -----------------------------------------------------------------


class RunSummary(BaseModel):
    """`GET /runs` 의 `items[]` 원소 - `RunDetailResponse` 와 같은 열. 요청 주체가 없는 행
    (Workflow 가 선언한 자식 Run)은 `requested_by` 가 null 입니다."""

    run_id: UUID
    agent_id: UUID
    agent_version: int
    status: RunStatus
    requested_at: datetime
    requested_by: UUID | None
    started_at: datetime | None
    finished_at: datetime | None
    failure_reason: FailureReason | None
    trace_id: str | None
    cancel_requested_at: datetime | None


class ListRunsResponse(BaseModel):
    """`GET /runs` 의 성공 응답."""

    items: list[RunSummary]
    next_cursor: str | None = None


class WorkflowSummary(BaseModel):
    """`GET /workflows` 의 `items[]` 원소 - 노드·간선 없이 이름과 현재 Version 번호."""

    id: UUID
    name: str
    current_version: int
    created_at: datetime
    updated_at: datetime


class ListWorkflowsResponse(BaseModel):
    """`GET /workflows` 의 성공 응답."""

    items: list[WorkflowSummary]
    next_cursor: str | None = None


class WorkflowRunSummary(BaseModel):
    """`GET /workflow-runs` 의 `items[]` 원소 - `WorkflowRunDetailResponse` 와 같은 열."""

    workflow_run_id: UUID
    workflow_id: UUID
    workflow_version: int
    workflow_version_id: UUID
    status: WorkflowRunStatus
    current_node_id: str | None
    waiting_run_id: UUID | None
    waiting_node_execution_id: UUID | None
    wake_at: datetime | None
    requested_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    failure_reason: str | None


class ListWorkflowRunsResponse(BaseModel):
    """`GET /workflow-runs` 의 성공 응답."""

    items: list[WorkflowRunSummary]
    next_cursor: str | None = None


class KnowledgeSetSummary(BaseModel):
    """`GET /knowledge-sets` 의 `items[]` 원소."""

    id: UUID
    name: str
    created_at: datetime


class ListKnowledgeSetsResponse(BaseModel):
    """`GET /knowledge-sets` 의 성공 응답."""

    items: list[KnowledgeSetSummary]
    next_cursor: str | None = None


class IngestionSummary(BaseModel):
    """`GET /knowledge-sets/{id}/ingestions` 의 `items[]` 원소(상세 응답과 같은 열)."""

    ingestion_id: UUID
    knowledge_set_id: UUID
    source: str
    status: IngestionStatus
    requested_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    failure_reason: str | None


class ListIngestionsResponse(BaseModel):
    """`GET /knowledge-sets/{id}/ingestions` 의 성공 응답."""

    items: list[IngestionSummary]
    next_cursor: str | None = None


# --- 라우터 -------------------------------------------------------------------


def _invalid_cursor() -> HTTPException:
    """깨진 `cursor` 는 요청 오류 - 여섯 목록 경로(`/agents` 포함)가 같은 응답을 냅니다."""
    return HTTPException(status_code=422, detail="invalid_cursor")


def build_listings_router(
    principal_dep: Callable[[Request], Principal],
    list_runs: ListRuns,
    list_workflows: ListWorkflows,
    list_workflow_runs: ListWorkflowRuns,
    list_knowledge_sets: ListKnowledgeSets,
    list_ingestions: ListIngestions,
) -> APIRouter:
    """목록 5경로를 등록합니다. 전부 `principal_dep` 뒤에 있습니다. 유스케이스는 inbound 포트
    **타입**으로만 받습니다(AR-12) - 구현은 조립(`main.py`)이 건네줍니다."""
    router = APIRouter()
    require_principal_dep = Annotated[Principal, Depends(principal_dep)]

    @router.get(
        "/runs",
        response_model=ListRunsResponse,
        responses={401: {"description": "unauthorized"}},
    )
    def list_runs_route(
        principal: require_principal_dep,
        limit: int = Query(default=50, ge=1, le=200),
        cursor: str | None = Query(default=None),
        status: Annotated[RunStatus | None, Query(description="이 상태의 Run 만")] = None,
    ) -> ListRunsResponse:
        del principal
        try:
            page = list_runs(limit, cursor, status)
        except InvalidCursor:
            raise _invalid_cursor() from None
        return ListRunsResponse(
            items=[
                RunSummary(
                    run_id=run.run_id,
                    agent_id=run.agent_id,
                    agent_version=run.agent_version,
                    status=run.status,
                    requested_at=run.requested_at,
                    requested_by=run.requested_by,
                    started_at=run.started_at,
                    finished_at=run.finished_at,
                    failure_reason=run.failure_reason,
                    trace_id=run.trace_id,
                    cancel_requested_at=run.cancel_requested_at,
                )
                for run in page.items
            ],
            next_cursor=page.next_cursor,
        )

    @router.get(
        "/workflows",
        response_model=ListWorkflowsResponse,
        responses={401: {"description": "unauthorized"}},
    )
    def list_workflows_route(
        principal: require_principal_dep,
        limit: int = Query(default=50, ge=1, le=200),
        cursor: str | None = Query(default=None),
    ) -> ListWorkflowsResponse:
        del principal
        try:
            page = list_workflows(limit, cursor)
        except InvalidCursor:
            raise _invalid_cursor() from None
        return ListWorkflowsResponse(
            items=[
                WorkflowSummary(
                    id=workflow.id,
                    name=workflow.name,
                    current_version=workflow.current_version,
                    created_at=workflow.created_at,
                    updated_at=workflow.updated_at,
                )
                for workflow in page.items
            ],
            next_cursor=page.next_cursor,
        )

    @router.get(
        "/workflow-runs",
        response_model=ListWorkflowRunsResponse,
        responses={401: {"description": "unauthorized"}},
    )
    def list_workflow_runs_route(
        principal: require_principal_dep,
        limit: int = Query(default=50, ge=1, le=200),
        cursor: str | None = Query(default=None),
        status: Annotated[
            WorkflowRunStatus | None, Query(description="이 상태의 Workflow Run 만")
        ] = None,
    ) -> ListWorkflowRunsResponse:
        del principal
        try:
            page = list_workflow_runs(limit, cursor, status)
        except InvalidCursor:
            raise _invalid_cursor() from None
        return ListWorkflowRunsResponse(
            items=[
                WorkflowRunSummary(
                    workflow_run_id=run.workflow_run_id,
                    workflow_id=run.workflow_id,
                    workflow_version=run.workflow_version,
                    workflow_version_id=run.workflow_version_id,
                    status=run.status,
                    current_node_id=run.current_node_id,
                    waiting_run_id=run.waiting_run_id,
                    waiting_node_execution_id=run.waiting_node_execution_id,
                    wake_at=run.wake_at,
                    requested_at=run.requested_at,
                    started_at=run.started_at,
                    finished_at=run.finished_at,
                    failure_reason=run.failure_reason,
                )
                for run in page.items
            ],
            next_cursor=page.next_cursor,
        )

    @router.get(
        "/knowledge-sets",
        response_model=ListKnowledgeSetsResponse,
        responses={401: {"description": "unauthorized"}},
    )
    def list_knowledge_sets_route(
        principal: require_principal_dep,
        limit: int = Query(default=50, ge=1, le=200),
        cursor: str | None = Query(default=None),
    ) -> ListKnowledgeSetsResponse:
        del principal
        try:
            page = list_knowledge_sets(limit, cursor)
        except InvalidCursor:
            raise _invalid_cursor() from None
        return ListKnowledgeSetsResponse(
            items=[
                KnowledgeSetSummary(id=s.id, name=s.name, created_at=s.created_at)
                for s in page.items
            ],
            next_cursor=page.next_cursor,
        )

    @router.get(
        "/knowledge-sets/{knowledge_set_id}/ingestions",
        response_model=ListIngestionsResponse,
        responses={
            401: {"description": "unauthorized"},
            404: {"description": "knowledge_set_not_found"},
        },
    )
    def list_ingestions_route(
        knowledge_set_id: UUID,
        principal: require_principal_dep,
        limit: int = Query(default=50, ge=1, le=200),
        cursor: str | None = Query(default=None),
        status: Annotated[IngestionStatus | None, Query(description="이 상태의 적재만")] = None,
    ) -> ListIngestionsResponse:
        del principal
        try:
            page = list_ingestions(knowledge_set_id, limit, cursor, status)
        except KnowledgeSetNotFound:
            raise HTTPException(status_code=404, detail="knowledge_set_not_found") from None
        except InvalidCursor:
            raise _invalid_cursor() from None
        return ListIngestionsResponse(
            items=[
                IngestionSummary(
                    ingestion_id=i.id,
                    knowledge_set_id=i.knowledge_set_id,
                    source=i.source,
                    status=i.status,
                    requested_at=i.requested_at,
                    started_at=i.started_at,
                    finished_at=i.finished_at,
                    failure_reason=i.failure_reason,
                )
                for i in page.items
            ],
            next_cursor=page.next_cursor,
        )

    return router
