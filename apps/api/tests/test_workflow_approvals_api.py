"""spec 0005 2.6 개정 5, R-8, R-12, C-4 (P4-4): 승인 HTTP 라우터 -- fake 저장소로 컨테이너 없이.

`POST /workflow-runs/{id}/approvals` 는 201 과 승인 기록, 거부 조건은 전부 4xx 와
`{"detail": "<코드>"}`(기존 라우터와 같은 모양), `GET /workflow-runs/{id}/approvals` 는 승인
기록 목록입니다. 인증은 `test_routes_require_auth.py` 가 전 경로에 대해 따로 증명합니다.
`approved_by` 가 **인증된 주체의 id 그대로** 인지가 이 파일의 핵심 판정입니다(H-1).
"""

from __future__ import annotations

from uuid import UUID, uuid4

from aether_api.adapters.inbound.http.workflow_approvals import build_workflow_approvals_router
from aether_api.application.usecases.approve_workflow_node import ApproveWorkflowNodeUseCase
from aether_api.application.usecases.list_workflow_approvals import ListWorkflowApprovalsUseCase
from aether_api.domain.api_key import Principal
from aether_workflow.domain.node import Edge, Node, NodeKind
from aether_workflow.domain.run_status import WorkflowRunStatus
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from apps.api.tests.fakes_workflow import (
    FakeWorkflowApprovalStore,
    FakeWorkflowRepository,
    FakeWorkflowRunDeclarationStore,
    FakeWorkflowRunNotifier,
)

_KEY = uuid4()


def _principal(request: Request) -> Principal:
    del request
    return Principal(key_id=_KEY, label="unit")


class _Rig:
    def __init__(self) -> None:
        self.repo = FakeWorkflowRepository()
        self.runs = FakeWorkflowRunDeclarationStore(self.repo)
        self.approvals = FakeWorkflowApprovalStore()
        self.notifier = FakeWorkflowRunNotifier()
        app = FastAPI()
        app.include_router(
            build_workflow_approvals_router(
                _principal,
                ApproveWorkflowNodeUseCase(self.runs, self.approvals, self.notifier),
                ListWorkflowApprovalsUseCase(self.runs, self.approvals),
            )
        )
        self.client = TestClient(app)

    def run(self, status: WorkflowRunStatus, awaited: UUID | None = None) -> UUID:
        workflow = self.repo.create(
            "wf", (Node("s", NodeKind.START), Node("e", NodeKind.END)), (Edge("s", "e"),)
        )
        view = self.runs.create(workflow.id, 1, None, uuid4())
        self.runs.apply_status(
            view.workflow_run_id,
            seq=1,
            status=status,
            current_node_id="gate",
            waiting_run_id=None,
            started_at=None,
            finished_at=None,
            failure_reason=None,
            waiting_node_execution_id=awaited,
        )
        return view.workflow_run_id

    def waiting(self) -> tuple[UUID, UUID]:
        awaited = uuid4()
        return self.run(WorkflowRunStatus.WAITING_APPROVAL, awaited), awaited


def test_post_returns_201_with_the_record_and_the_authenticated_principal_as_approver() -> None:
    rig = _Rig()
    run_id, awaited = rig.waiting()

    response = rig.client.post(
        f"/workflow-runs/{run_id}/approvals",
        json={"node_execution_id": str(awaited), "note": "looks fine"},
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["workflow_run_id"] == str(run_id)
    assert body["node_execution_id"] == str(awaited)
    assert body["approved_by"] == str(_KEY), "인증된 주체의 id 를 그대로 적는다 - 판정하지 않는다"
    assert body["note"] == "looks fine"
    assert body["approved_at"] is not None
    assert len(rig.notifier.calls) == 1


def test_the_note_is_optional() -> None:
    rig = _Rig()
    run_id, awaited = rig.waiting()

    response = rig.client.post(
        f"/workflow-runs/{run_id}/approvals", json={"node_execution_id": str(awaited)}
    )

    assert response.status_code == 201, response.text
    assert response.json()["note"] is None


def test_post_to_an_unknown_run_is_404_workflow_run_not_found() -> None:
    rig = _Rig()

    response = rig.client.post(
        f"/workflow-runs/{uuid4()}/approvals", json={"node_execution_id": str(uuid4())}
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "workflow_run_not_found"}


def test_post_to_a_run_that_is_not_waiting_is_400_workflow_run_not_waiting_approval() -> None:
    rig = _Rig()
    run_id = rig.run(WorkflowRunStatus.RUNNING)

    response = rig.client.post(
        f"/workflow-runs/{run_id}/approvals", json={"node_execution_id": str(uuid4())}
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "workflow_run_not_waiting_approval"}
    assert rig.approvals.approvals == []


def test_post_naming_a_node_execution_that_is_not_awaited_is_400_node_execution_not_waiting() -> (
    None
):
    rig = _Rig()
    run_id, _awaited = rig.waiting()

    response = rig.client.post(
        f"/workflow-runs/{run_id}/approvals", json={"node_execution_id": str(uuid4())}
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "node_execution_not_waiting"}
    assert rig.approvals.approvals == []
    assert rig.notifier.calls == []


def test_post_twice_is_400_already_approved_and_leaves_one_record() -> None:
    rig = _Rig()
    run_id, awaited = rig.waiting()
    body = {"node_execution_id": str(awaited)}
    first = rig.client.post(f"/workflow-runs/{run_id}/approvals", json=body)

    second = rig.client.post(f"/workflow-runs/{run_id}/approvals", json=body)

    assert first.status_code == 201
    assert second.status_code == 400
    assert second.json() == {"detail": "already_approved"}
    assert len(rig.approvals.approvals) == 1
    assert len(rig.notifier.calls) == 1


def test_post_without_the_target_node_execution_is_422() -> None:
    """승인은 **특정 노드 실행을 지목**해야 한다 - 지목 없는 승인은 요청 검증에서 막힌다."""
    rig = _Rig()
    run_id, _awaited = rig.waiting()

    response = rig.client.post(f"/workflow-runs/{run_id}/approvals", json={"note": "x"})

    assert response.status_code == 422
    assert rig.approvals.approvals == []


def test_get_lists_the_approval_records_of_the_run() -> None:
    """R-12: 승인 기록이 조회에 나온다 - `approved_by`·`approved_at`·대상 노드 실행."""
    rig = _Rig()
    run_id, awaited = rig.waiting()
    rig.client.post(
        f"/workflow-runs/{run_id}/approvals", json={"node_execution_id": str(awaited), "note": "n"}
    )

    response = rig.client.get(f"/workflow-runs/{run_id}/approvals")

    assert response.status_code == 200, response.text
    (item,) = response.json()["items"]
    assert item["node_execution_id"] == str(awaited)
    assert item["approved_by"] == str(_KEY)
    assert item["approved_at"] is not None
    assert item["note"] == "n"


def test_get_for_a_run_without_approvals_is_an_empty_list_and_unknown_is_404() -> None:
    rig = _Rig()
    run_id, _awaited = rig.waiting()

    empty = rig.client.get(f"/workflow-runs/{run_id}/approvals")
    unknown = rig.client.get(f"/workflow-runs/{uuid4()}/approvals")

    assert empty.status_code == 200
    assert empty.json() == {"items": []}
    assert unknown.status_code == 404
    assert unknown.json() == {"detail": "workflow_run_not_found"}
