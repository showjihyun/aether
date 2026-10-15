"""spec 0005 2.6, R-12 (P4-4): `ListWorkflowApprovalsUseCase` -- 승인 기록이 **조회에 나온다**
(`approved_by`·`approved_at`·대상 노드 실행). fake 포트로, 컨테이너 없이(AR-9)."""

from __future__ import annotations

from uuid import uuid4

import pytest
from aether_api.application.usecases.list_workflow_approvals import ListWorkflowApprovalsUseCase
from aether_api.domain.workflow_run import WorkflowRunNotFound, WorkflowRunView
from aether_workflow.domain.node import Edge, Node, NodeKind

from apps.api.tests.fakes_workflow import (
    FakeWorkflowApprovalStore,
    FakeWorkflowRepository,
    FakeWorkflowRunDeclarationStore,
)


class _Rig:
    def __init__(self) -> None:
        self.repo = FakeWorkflowRepository()
        self.runs = FakeWorkflowRunDeclarationStore(self.repo)
        self.approvals = FakeWorkflowApprovalStore()
        self.list = ListWorkflowApprovalsUseCase(self.runs, self.approvals)

    def run(self) -> WorkflowRunView:
        workflow = self.repo.create(
            "wf", (Node("s", NodeKind.START), Node("e", NodeKind.END)), (Edge("s", "e"),)
        )
        return self.runs.create(workflow.id, 1, None, uuid4())


def test_an_unknown_run_is_not_found() -> None:
    with pytest.raises(WorkflowRunNotFound):
        _Rig().list(uuid4())


def test_a_run_without_approvals_lists_nothing() -> None:
    rig = _Rig()

    assert rig.list(rig.run().workflow_run_id) == ()


def test_the_stored_approvals_of_that_run_only_are_listed_with_who_when_and_what() -> None:
    rig = _Rig()
    mine, other = rig.run(), rig.run()
    first, second = uuid4(), uuid4()
    rig.approvals.record(mine.workflow_run_id, first, "key-a", "n1")
    rig.approvals.record(mine.workflow_run_id, second, "key-b", None)
    rig.approvals.record(other.workflow_run_id, uuid4(), "key-c", None)

    listed = rig.list(mine.workflow_run_id)

    assert [(a.node_execution_id, a.approved_by, a.note) for a in listed] == [
        (first, "key-a", "n1"),
        (second, "key-b", None),
    ]
    assert all(a.approved_at is not None for a in listed)
