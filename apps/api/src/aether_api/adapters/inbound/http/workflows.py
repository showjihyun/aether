"""spec 0005 2.2, R-1, R-2, D-12: Workflow 정의 HTTP 계약과 라우터.

`POST /workflows` · `GET /workflows/{id}` · `PUT /workflows/{id}`(새 Version) ·
`GET /workflows/{id}/versions/{version}`. 전 경로가 `require_principal(app.state.
authenticate)` 뒤에 있습니다. 오류 응답은 `{"detail": "<코드>"}` 입니다.

검증 실패(R-1)는 **400 `invalid_workflow_graph`** 이고 본문에 `violations[]` 가 붙습니다 —
각 원소의 `reason` 이 `aether_workflow.domain.validation.Reason` 의 값(열한 개 중 하나)이라
호출자가 사유를 구별합니다. 422 를 쓰지 않는 이유: 422 는 FastAPI 요청 검증(배열 형태)이
이미 쓰고 있어 sdk 가 두 모양을 한 상태 코드에서 가려야 하기 때문입니다.

`aether_workflow.domain` 만 import 합니다(`application`·`adapters` 는 import 하지 않습니다).

의도적으로 `from __future__ import annotations` 을 쓰지 않습니다 — `knowledge.py`/
`agents.py` 와 같은 이유(PEP 563 이 팩토리 지역 변수를 캡처한 `Annotated[...]` 의존성을
깨뜨립니다, improvement-log 2026-09-11-017).
"""

from collections.abc import Callable
from typing import Annotated
from uuid import UUID

from aether_workflow.domain.condition import ConditionOperator
from aether_workflow.domain.node import Edge, Node, NodeKind
from aether_workflow.domain.validation import InvalidWorkflowGraph
from aether_workflow.domain.workflow_version import WorkflowVersion
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from aether_api.application.ports.inbound.workflows import (
    DefineWorkflow,
    DefineWorkflowRequest,
    GetWorkflow,
    GetWorkflowVersion,
    UpdateWorkflow,
    UpdateWorkflowRequest,
)
from aether_api.domain.api_key import Principal
from aether_api.domain.workflow import WorkflowNotFound, WorkflowView

# --- 요청·응답 모델 ------------------------------------------------------------


class NodeModel(BaseModel):
    # `max_iterations` 는 `LOOP` 에서, `agent_id`·`agent_version` 은 `AGENT` 에서만 뜻이 있습니다
    # (spec 0005 2.2 개정 3). 셋 다 선택 키이고 다른 종류의 노드에 있는 값은 무시됩니다.
    # `CONDITION` 은 `condition_path`·`condition_operator`·`condition_value`(`exists` 면 값 없음)를
    # 가지고 분기는 간선 `label` 의 `true`·`false` 입니다(개정 4).
    # (docstring 이 아닌 이유: OpenAPI `description` 이 늘어 SDK 의 변경이 두 키 밖으로 번집니다.)

    id: str
    kind: NodeKind
    max_iterations: int | None = None
    agent_id: UUID | None = None
    agent_version: int | None = None
    condition_path: str | None = None
    condition_operator: ConditionOperator | None = None
    condition_value: str | int | float | bool | None = None


class EdgeModel(BaseModel):
    source: str
    target: str
    label: str | None = None


class CreateWorkflowRequest(BaseModel):
    """`POST /workflows` 의 요청 본문."""

    name: str
    nodes: list[NodeModel]
    edges: list[EdgeModel]


class UpdateWorkflowBody(BaseModel):
    """`PUT /workflows/{id}` 의 요청 본문 — 이름은 바꾸지 않습니다(새 Version 만)."""

    nodes: list[NodeModel]
    edges: list[EdgeModel]


class WorkflowResponse(BaseModel):
    """`POST`·`GET`·`PUT /workflows` 의 성공 응답 — 최신 Version 을 함께 돌려줍니다."""

    id: UUID
    name: str
    current_version: int
    nodes: list[NodeModel]
    edges: list[EdgeModel]


class WorkflowVersionResponse(BaseModel):
    """`GET /workflows/{id}/versions/{version}` 의 성공 응답."""

    workflow_id: UUID
    version: int
    nodes: list[NodeModel]
    edges: list[EdgeModel]


class ViolationModel(BaseModel):
    reason: str
    node_id: str | None


class InvalidWorkflowGraphResponse(BaseModel):
    """400 본문: `detail` 은 항상 `invalid_workflow_graph`."""

    detail: str
    violations: list[ViolationModel]


def _nodes_in(models: list[NodeModel]) -> tuple[Node, ...]:
    return tuple(
        Node(
            id=m.id,
            kind=m.kind,
            max_iterations=m.max_iterations,
            agent_id=m.agent_id,
            agent_version=m.agent_version,
            condition_path=m.condition_path,
            condition_operator=m.condition_operator,
            condition_value=m.condition_value,
        )
        for m in models
    )


def _edges_in(models: list[EdgeModel]) -> tuple[Edge, ...]:
    return tuple(Edge(source=m.source, target=m.target, label=m.label) for m in models)


def _nodes_out(version: WorkflowVersion) -> list[NodeModel]:
    return [
        NodeModel(
            id=n.id,
            kind=n.kind,
            max_iterations=n.max_iterations,
            agent_id=n.agent_id,
            agent_version=n.agent_version,
            condition_path=n.condition_path,
            condition_operator=n.condition_operator,
            condition_value=n.condition_value,
        )
        for n in version.nodes
    ]


def _edges_out(version: WorkflowVersion) -> list[EdgeModel]:
    return [EdgeModel(source=e.source, target=e.target, label=e.label) for e in version.edges]


def _to_response(view: WorkflowView) -> WorkflowResponse:
    return WorkflowResponse(
        id=view.id,
        name=view.name,
        current_version=view.latest_version.number,
        nodes=_nodes_out(view.latest_version),
        edges=_edges_out(view.latest_version),
    )


def _invalid_graph(exc: InvalidWorkflowGraph) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={
            "detail": "invalid_workflow_graph",
            "violations": [
                {"reason": v.reason.value, "node_id": v.node_id} for v in exc.violations
            ],
        },
    )


def _workflow_not_found() -> HTTPException:
    return HTTPException(status_code=404, detail="workflow_not_found")


def _workflow_version_not_found() -> HTTPException:
    return HTTPException(status_code=404, detail="workflow_version_not_found")


# --- 라우터 -------------------------------------------------------------------


def build_workflows_router(
    principal_dep: Callable[[Request], Principal],
    define_workflow: DefineWorkflow,
    get_workflow: GetWorkflow,
    update_workflow: UpdateWorkflow,
    get_workflow_version: GetWorkflowVersion,
) -> APIRouter:
    router = APIRouter()
    require_principal_dep = Annotated[Principal, Depends(principal_dep)]

    @router.post(
        "/workflows",
        response_model=WorkflowResponse,
        status_code=status.HTTP_201_CREATED,
        responses={
            400: {"model": InvalidWorkflowGraphResponse, "description": "invalid_workflow_graph"},
            401: {"description": "unauthorized"},
        },
    )
    def define_workflow_route(
        body: CreateWorkflowRequest,
        principal: require_principal_dep,
    ) -> WorkflowResponse | JSONResponse:
        del principal
        try:
            view = define_workflow(
                DefineWorkflowRequest(
                    name=body.name, nodes=_nodes_in(body.nodes), edges=_edges_in(body.edges)
                )
            )
        except InvalidWorkflowGraph as exc:
            return _invalid_graph(exc)
        return _to_response(view)

    @router.get(
        "/workflows/{workflow_id}",
        response_model=WorkflowResponse,
        responses={
            401: {"description": "unauthorized"},
            404: {"description": "workflow_not_found"},
        },
    )
    def get_workflow_route(workflow_id: UUID, principal: require_principal_dep) -> WorkflowResponse:
        del principal
        view = get_workflow(workflow_id)
        if view is None:
            raise _workflow_not_found()
        return _to_response(view)

    @router.put(
        "/workflows/{workflow_id}",
        response_model=WorkflowResponse,
        responses={
            400: {"model": InvalidWorkflowGraphResponse, "description": "invalid_workflow_graph"},
            401: {"description": "unauthorized"},
            404: {"description": "workflow_not_found"},
        },
    )
    def update_workflow_route(
        workflow_id: UUID,
        body: UpdateWorkflowBody,
        principal: require_principal_dep,
    ) -> WorkflowResponse | JSONResponse:
        del principal
        try:
            view = update_workflow(
                UpdateWorkflowRequest(
                    workflow_id=workflow_id,
                    nodes=_nodes_in(body.nodes),
                    edges=_edges_in(body.edges),
                )
            )
        except InvalidWorkflowGraph as exc:
            return _invalid_graph(exc)
        except WorkflowNotFound:
            raise _workflow_not_found() from None
        return _to_response(view)

    @router.get(
        "/workflows/{workflow_id}/versions/{version}",
        response_model=WorkflowVersionResponse,
        responses={
            401: {"description": "unauthorized"},
            404: {"description": "workflow_version_not_found"},
        },
    )
    def get_workflow_version_route(
        workflow_id: UUID, version: int, principal: require_principal_dep
    ) -> WorkflowVersionResponse:
        del principal
        found = get_workflow_version(workflow_id, version)
        if found is None:
            raise _workflow_version_not_found()
        return WorkflowVersionResponse(
            workflow_id=workflow_id,
            version=found.number,
            nodes=_nodes_out(found),
            edges=_edges_out(found),
        )

    return router
