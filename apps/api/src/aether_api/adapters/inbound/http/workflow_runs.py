"""spec 0005 2.2, 2.3, R-13: Workflow Run HTTP 계약과 라우터.

`POST /workflows/{workflow_id}/runs`(202) · `GET /workflow-runs/{workflow_run_id}`. 전 경로가
`principal_dep` 뒤에 있습니다(`test_routes_require_auth.py` 가 전 경로를 확인합니다). 오류
응답은 `{"detail": "<코드>"}` 이고 422(요청 검증 실패)는 FastAPI 기본 형태를 그대로 둡니다.

`status` 는 `aether_workflow.domain.run_status.WorkflowRunStatus` 를 그대로 씁니다 — api 는
`aether_workflow.domain` 만 import 합니다. `waiting_run`·`waiting_approval` 이 상태만으로
구별됩니다(R-13). `waiting_node_execution_id` 는 `waiting_approval` 일 때 승인이 지목해야 하는
노드 실행의 id 입니다(P4-4, R-12). `wake_at` 은 `waiting_timer`(`WAIT` 노드의 파킹)일 때 깨어날
시각입니다(P4-3) - 대기가 아니면 `null` 입니다.

의도적으로 `from __future__ import annotations` 을 쓰지 않습니다 — `runs.py`·`workflows.py`
와 같은 이유(PEP 563 이 팩토리 지역 변수를 캡처한 `Annotated[...]` 의존성을 깨뜨립니다,
improvement-log 2026-09-11-017).
"""

from collections.abc import Callable
from datetime import datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from aether_workflow.domain.run_status import WorkflowRunStatus
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel

from aether_api.application.ports.inbound.workflow_runs import GetWorkflowRun, StartWorkflowRun
from aether_api.domain.api_key import Principal
from aether_api.domain.workflow import WorkflowNotFound, WorkflowVersionNotFound
from aether_api.domain.workflow_run import WorkflowRunNotFound

# --- 요청·응답 모델 ------------------------------------------------------------


class WorkflowRunRequest(BaseModel):
    """`POST /workflows/{workflow_id}/runs` 의 요청 본문."""

    input: dict[str, Any] | None = None
    workflow_version: int | None = None


class WorkflowRunAccepted(BaseModel):
    """`POST` 의 성공 응답(202) — Workflow Run 은 항상 `queued` 로 시작합니다."""

    workflow_run_id: UUID
    workflow_id: UUID
    workflow_version: int
    status: Literal["queued"] = "queued"
    requested_at: datetime


class WorkflowRunDetailResponse(BaseModel):
    """`GET /workflow-runs/{workflow_run_id}` 의 성공 응답 — `control.workflow_runs` 투영."""

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


# --- 라우터 -------------------------------------------------------------------


def build_workflow_runs_router(
    principal_dep: Callable[[Request], Principal],
    start_workflow_run: StartWorkflowRun,
    get_workflow_run: GetWorkflowRun,
) -> APIRouter:
    """두 경로를 등록합니다. 전부 `principal_dep` 뒤에 있습니다. 유스케이스는 inbound 포트
    **타입**으로만 받습니다(AR-12) — 구현은 조립(`main.py`)이 건네줍니다."""
    router = APIRouter()
    require_principal_dep = Annotated[Principal, Depends(principal_dep)]

    @router.post(
        "/workflows/{workflow_id}/runs",
        response_model=WorkflowRunAccepted,
        status_code=status.HTTP_202_ACCEPTED,
        responses={
            401: {"description": "unauthorized"},
            404: {"description": "workflow_not_found | workflow_version_not_found"},
        },
    )
    def start_workflow_run_route(
        workflow_id: UUID,
        body: WorkflowRunRequest,
        principal: require_principal_dep,
    ) -> WorkflowRunAccepted:
        try:
            view = start_workflow_run(
                workflow_id, body.input, body.workflow_version, principal.key_id
            )
        except WorkflowNotFound:
            raise HTTPException(status_code=404, detail="workflow_not_found") from None
        except WorkflowVersionNotFound:
            raise HTTPException(status_code=404, detail="workflow_version_not_found") from None
        return WorkflowRunAccepted(
            workflow_run_id=view.workflow_run_id,
            workflow_id=view.workflow_id,
            workflow_version=view.workflow_version,
            requested_at=view.requested_at,
        )

    @router.get(
        "/workflow-runs/{workflow_run_id}",
        response_model=WorkflowRunDetailResponse,
        responses={
            401: {"description": "unauthorized"},
            404: {"description": "workflow_run_not_found"},
        },
    )
    def get_workflow_run_route(
        workflow_run_id: UUID,
        principal: require_principal_dep,
    ) -> WorkflowRunDetailResponse:
        del principal
        try:
            view = get_workflow_run(workflow_run_id)
        except WorkflowRunNotFound:
            raise HTTPException(status_code=404, detail="workflow_run_not_found") from None
        return WorkflowRunDetailResponse(
            workflow_run_id=view.workflow_run_id,
            workflow_id=view.workflow_id,
            workflow_version=view.workflow_version,
            workflow_version_id=view.workflow_version_id,
            status=view.status,
            current_node_id=view.current_node_id,
            waiting_run_id=view.waiting_run_id,
            waiting_node_execution_id=view.waiting_node_execution_id,
            wake_at=view.wake_at,
            requested_at=view.requested_at,
            started_at=view.started_at,
            finished_at=view.finished_at,
            failure_reason=view.failure_reason,
        )

    return router
