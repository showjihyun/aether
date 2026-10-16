"""spec 0005 2.6 개정 5, R-8, R-12, C-4 (P4-4): 승인 HTTP 계약과 라우터.

`POST /workflow-runs/{workflow_run_id}/approvals`(201) · `GET /workflow-runs/{workflow_run_id}/
approvals`. 전 경로가 `principal_dep` 뒤에 있습니다(`test_routes_require_auth.py` 가 전 경로를
확인합니다). 오류 응답은 `{"detail": "<코드>"}` 이고 422(요청 검증 실패)는 FastAPI 기본 형태를
그대로 둡니다.

**권한 판정이 없습니다.** 인증된 주체 누구나 승인할 수 있습니다. `approved_by` 는 `Principal.key_id`
를 **그대로** 문자열로 적습니다 - 이 라우터는 그 주체가 승인할 자격이 있는지 묻지 않습니다(C-4,
Phase 8 의 자리). 거부 조건은 전부 400/404 의 **정확성** 가드입니다:

| 코드 | 상태 | 뜻 |
| --- | --- | --- |
| `workflow_run_not_found` | 404 | 없는 Workflow Run |
| `workflow_run_not_waiting_approval` | 400 | Run 이 `waiting_approval` 이 아님(선승인) |
| `node_execution_not_waiting` | 400 | 지목한 노드 실행이 그 Run 이 기다리는 것이 아님(R-12) |
| `already_approved` | 400 | 그 노드 실행의 승인이 이미 기록됨(R-8) |

의도적으로 `from __future__ import annotations` 을 쓰지 않습니다 - `workflow_runs.py` 와 같은 이유
(PEP 563 이 팩토리 지역 변수를 캡처한 `Annotated[...]` 의존성을 깨뜨립니다, improvement-log
2026-09-11-017).
"""

from collections.abc import Callable
from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel

from aether_api.application.ports.inbound.workflow_approvals import (
    ApproveWorkflowNode,
    ListWorkflowApprovals,
)
from aether_api.domain.api_key import Principal
from aether_api.domain.workflow_approval import (
    AlreadyApproved,
    NodeExecutionNotWaiting,
    WorkflowApprovalView,
    WorkflowRunNotWaitingApproval,
)
from aether_api.domain.workflow_run import WorkflowRunNotFound

# --- 요청·응답 모델 ------------------------------------------------------------


class ApprovalRequest(BaseModel):
    """`POST /workflow-runs/{id}/approvals` 의 요청 본문 - **지목하는 노드 실행** 이 필수입니다."""

    node_execution_id: UUID
    note: str | None = None


class ApprovalResponse(BaseModel):
    """승인 기록 한 건 - `approved_by` 는 인증된 주체의 id 그대로입니다."""

    workflow_run_id: UUID
    node_execution_id: UUID
    approved_by: str
    approved_at: datetime
    note: str | None


class ApprovalListResponse(BaseModel):
    items: list[ApprovalResponse]


def _response(view: WorkflowApprovalView) -> ApprovalResponse:
    return ApprovalResponse(
        workflow_run_id=view.workflow_run_id,
        node_execution_id=view.node_execution_id,
        approved_by=view.approved_by,
        approved_at=view.approved_at,
        note=view.note,
    )


# --- 라우터 -------------------------------------------------------------------


def build_workflow_approvals_router(
    principal_dep: Callable[[Request], Principal],
    approve_workflow_node: ApproveWorkflowNode,
    list_workflow_approvals: ListWorkflowApprovals,
) -> APIRouter:
    """두 경로를 등록합니다. 전부 `principal_dep` 뒤에 있습니다. 유스케이스는 inbound 포트
    **타입**으로만 받습니다(AR-12) - 구현은 조립(`main.py`)이 건네줍니다."""
    router = APIRouter()
    require_principal_dep = Annotated[Principal, Depends(principal_dep)]

    @router.post(
        "/workflow-runs/{workflow_run_id}/approvals",
        response_model=ApprovalResponse,
        status_code=status.HTTP_201_CREATED,
        responses={
            400: {
                "description": (
                    "workflow_run_not_waiting_approval | node_execution_not_waiting"
                    " | already_approved"
                )
            },
            401: {"description": "unauthorized"},
            404: {"description": "workflow_run_not_found"},
        },
    )
    def approve_route(
        workflow_run_id: UUID,
        body: ApprovalRequest,
        principal: require_principal_dep,
    ) -> ApprovalResponse:
        try:
            # 인증된 주체의 id 를 그대로 적는다 - 이 주체가 승인할 수 있는지는 묻지 않는다(C-4).
            view = approve_workflow_node(
                workflow_run_id, body.node_execution_id, str(principal.key_id), body.note
            )
        except WorkflowRunNotFound:
            raise HTTPException(status_code=404, detail="workflow_run_not_found") from None
        except AlreadyApproved:
            raise HTTPException(status_code=400, detail="already_approved") from None
        except WorkflowRunNotWaitingApproval:
            raise HTTPException(
                status_code=400, detail="workflow_run_not_waiting_approval"
            ) from None
        except NodeExecutionNotWaiting:
            raise HTTPException(status_code=400, detail="node_execution_not_waiting") from None
        return _response(view)

    @router.get(
        "/workflow-runs/{workflow_run_id}/approvals",
        response_model=ApprovalListResponse,
        responses={
            401: {"description": "unauthorized"},
            404: {"description": "workflow_run_not_found"},
        },
    )
    def list_approvals_route(
        workflow_run_id: UUID,
        principal: require_principal_dep,
    ) -> ApprovalListResponse:
        del principal
        try:
            views = list_workflow_approvals(workflow_run_id)
        except WorkflowRunNotFound:
            raise HTTPException(status_code=404, detail="workflow_run_not_found") from None
        return ApprovalListResponse(items=[_response(v) for v in views])

    return router
