"""spec 0007 2.3, 2.4, R-5, D-3, D-4 (P5-2): `GET /workflow-runs/{id}/nodes` 의 HTTP 계약과 라우터.

`GET /agents` 의 페이지 규칙을 그대로 따릅니다 - `limit`(기본 50, 1~200)·`cursor`·
`{items, next_cursor}`. 정렬은 `node_id` 오름차순입니다(노드당 한 행이라 안정적인 키).
**노드 출력은 응답에 없습니다**(D-4) - 투영에 없는 값이고 api 는 `data` 를 읽지 않습니다.
기존 라우터는 건드리지 않고 이 모듈이 따로 등록합니다(additive). 전 경로가 `principal_dep` 뒤에
있습니다(R-8).

의도적으로 `from __future__ import annotations` 을 쓰지 않습니다 - `listings.py` 와 같은 이유
(PEP 563 이 팩토리 지역 변수를 캡처한 `Annotated[...]` 의존성을 깨뜨립니다,
improvement-log 2026-09-11-017).
"""

from collections.abc import Callable
from datetime import datetime
from typing import Annotated
from uuid import UUID

from aether_workflow.domain.node_execution import NodeExecutionStatus
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel

from aether_api.application.ports.inbound.workflow_run_nodes import ListWorkflowRunNodes
from aether_api.domain.api_key import Principal
from aether_api.domain.cursor import InvalidCursor
from aether_api.domain.workflow_run import WorkflowRunNotFound


class WorkflowNodeState(BaseModel):
    """`GET /workflow-runs/{id}/nodes` 의 `items[]` 원소 - 노드 하나의 가장 최근 상태."""

    node_id: str
    kind: str
    status: NodeExecutionStatus
    started_at: datetime | None
    finished_at: datetime | None
    failure_reason: str | None


class ListWorkflowRunNodesResponse(BaseModel):
    """`GET /workflow-runs/{id}/nodes` 의 성공 응답."""

    items: list[WorkflowNodeState]
    next_cursor: str | None = None


def build_workflow_run_nodes_router(
    principal_dep: Callable[[Request], Principal],
    list_nodes: ListWorkflowRunNodes,
) -> APIRouter:
    router = APIRouter()
    require_principal_dep = Annotated[Principal, Depends(principal_dep)]

    @router.get(
        "/workflow-runs/{workflow_run_id}/nodes",
        response_model=ListWorkflowRunNodesResponse,
        responses={
            401: {"description": "unauthorized"},
            404: {"description": "workflow_run_not_found"},
        },
    )
    def list_workflow_run_nodes_route(
        workflow_run_id: UUID,
        principal: require_principal_dep,
        limit: int = Query(default=50, ge=1, le=200),
        cursor: str | None = Query(default=None),
    ) -> ListWorkflowRunNodesResponse:
        del principal
        try:
            page = list_nodes(workflow_run_id, limit, cursor)
        except WorkflowRunNotFound:
            raise HTTPException(status_code=404, detail="workflow_run_not_found") from None
        except InvalidCursor:
            raise HTTPException(status_code=422, detail="invalid_cursor") from None
        return ListWorkflowRunNodesResponse(
            items=[
                WorkflowNodeState(
                    node_id=n.node_id,
                    kind=n.kind,
                    status=n.status,
                    started_at=n.started_at,
                    finished_at=n.finished_at,
                    failure_reason=n.failure_reason,
                )
                for n in page.items
            ],
            next_cursor=page.next_cursor,
        )

    return router
