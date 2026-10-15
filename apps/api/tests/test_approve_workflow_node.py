"""spec 0005 2.6 개정 5, R-8, R-12, C-4 (P4-4): `ApproveWorkflowNodeUseCase` -- fake 포트로,
컨테이너
없이(AR-9).

증명하는 것: 승인은 **지목한 노드 실행이 그 Run 이 지금 기다리는 것일 때만** 기록된다(정확성 가드,
R-12) / 거부 조건 넷은 서로 다른 예외다 / 두 번째 승인은 `AlreadyApproved` 이고 기록은 1건·재큐는
1회(R-8) / 기록한 **뒤에** 재큐한다 / 재큐 실패가 기록을 되돌리거나 승인을 막지 않는다 / 그리고
**승인자를 판정하지 않는다** -- 요청자 본인이든 아무나든 같은 규칙으로 승인된다(C-4).
"""

from __future__ import annotations

import logging
from uuid import UUID, uuid4

import pytest
from aether_api.application.usecases.approve_workflow_node import ApproveWorkflowNodeUseCase
from aether_api.domain.workflow_approval import (
    AlreadyApproved,
    NodeExecutionNotWaiting,
    WorkflowRunNotWaitingApproval,
)
from aether_api.domain.workflow_run import WorkflowRunNotFound, WorkflowRunView
from aether_workflow.domain.node import Edge, Node, NodeKind
from aether_workflow.domain.run_status import WorkflowRunStatus

from apps.api.tests.fakes_workflow import (
    FakeWorkflowApprovalStore,
    FakeWorkflowRepository,
    FakeWorkflowRunDeclarationStore,
    FakeWorkflowRunNotifier,
)

_REQUESTER = uuid4()


class _Rig:
    def __init__(self, *, notifier: FakeWorkflowRunNotifier | None = None) -> None:
        self.repo = FakeWorkflowRepository()
        self.runs = FakeWorkflowRunDeclarationStore(self.repo)
        self.approvals = FakeWorkflowApprovalStore()
        self.notifier = notifier if notifier is not None else FakeWorkflowRunNotifier()
        self.approve = ApproveWorkflowNodeUseCase(self.runs, self.approvals, self.notifier)

    def run(self, status: WorkflowRunStatus = WorkflowRunStatus.QUEUED) -> WorkflowRunView:
        workflow = self.repo.create(
            "wf", (Node("s", NodeKind.START), Node("e", NodeKind.END)), (Edge("s", "e"),)
        )
        view = self.runs.create(workflow.id, 1, None, _REQUESTER)
        if status is not WorkflowRunStatus.QUEUED:
            self.project(view.workflow_run_id, status)
        return view

    def project(
        self,
        run_id: UUID,
        status: WorkflowRunStatus,
        *,
        awaited: UUID | None = None,
        seq: int = 1,
    ) -> None:
        self.runs.apply_status(
            run_id,
            seq=seq,
            status=status,
            current_node_id="gate",
            waiting_run_id=None,
            started_at=None,
            finished_at=None,
            failure_reason=None,
            waiting_node_execution_id=awaited,
        )

    def waiting_run(self) -> tuple[WorkflowRunView, UUID]:
        view = self.run()
        awaited = uuid4()
        self.project(view.workflow_run_id, WorkflowRunStatus.WAITING_APPROVAL, awaited=awaited)
        return view, awaited


def test_approving_the_awaited_node_execution_records_it_and_requeues_the_run() -> None:
    rig = _Rig()
    view, awaited = rig.waiting_run()

    approval = rig.approve(view.workflow_run_id, awaited, "key-123", "ok")

    assert approval.workflow_run_id == view.workflow_run_id
    assert approval.node_execution_id == awaited
    assert approval.approved_by == "key-123", "인증된 주체의 id 를 그대로 적는다"
    assert approval.note == "ok"
    assert rig.approvals.list_for(view.workflow_run_id) == (approval,)
    assert rig.notifier.calls == [(view.workflow_run_id, view.workflow_version_id, None)]


def test_the_approval_is_stored_before_the_run_is_requeued() -> None:
    """spec 2.6 개정 5 (3), (6): 재큐를 받은 실행기가 저장된 승인을 읽을 수 있어야 한다 -- 기록이
    재큐보다 먼저다."""
    rig = _Rig()
    view, awaited = rig.waiting_run()
    seen: list[bool] = []

    class _Spy(FakeWorkflowRunNotifier):
        def requested(
            self, workflow_run_id: UUID, workflow_version_id: UUID, traceparent: str | None
        ) -> None:
            seen.append(rig.approvals.get(workflow_run_id, awaited) is not None)
            super().requested(workflow_run_id, workflow_version_id, traceparent)

    rig.notifier = _Spy()
    rig.approve = ApproveWorkflowNodeUseCase(rig.runs, rig.approvals, rig.notifier)

    rig.approve(view.workflow_run_id, awaited, "k", None)

    assert seen == [True]


def test_an_unknown_run_is_not_found_and_nothing_is_recorded() -> None:
    rig = _Rig()

    with pytest.raises(WorkflowRunNotFound):
        rig.approve(uuid4(), uuid4(), "k", None)

    assert rig.approvals.approvals == []
    assert rig.notifier.calls == []


@pytest.mark.parametrize(
    "status",
    [
        WorkflowRunStatus.QUEUED,
        WorkflowRunStatus.RUNNING,
        WorkflowRunStatus.WAITING_RUN,
        WorkflowRunStatus.SUCCEEDED,
        WorkflowRunStatus.FAILED,
        WorkflowRunStatus.CANCELLED,
    ],
)
def test_a_run_that_is_not_waiting_for_approval_rejects_the_approval(
    status: WorkflowRunStatus,
) -> None:
    """R-12: 선승인을 막는다 -- 아직 승인 대기에 닿지 않은 Run(또는 다른 대기·종결)은 거부."""
    rig = _Rig()
    view = rig.run(status)

    with pytest.raises(WorkflowRunNotWaitingApproval):
        rig.approve(view.workflow_run_id, uuid4(), "k", None)

    assert rig.approvals.approvals == []
    assert rig.notifier.calls == []


def test_naming_a_node_execution_the_run_is_not_waiting_for_is_rejected() -> None:
    """R-12 의 핵심: 지목한 노드 실행이 이 Run 이 기다리는 것이 아니면 -- 다른 노드 실행이든
    존재하지 않는 id 든 -- 거부한다. 기록도 재큐도 없다."""
    rig = _Rig()
    view, awaited = rig.waiting_run()

    with pytest.raises(NodeExecutionNotWaiting):
        rig.approve(view.workflow_run_id, uuid4(), "k", None)
    with pytest.raises(NodeExecutionNotWaiting):
        rig.approve(view.workflow_run_id, UUID(int=awaited.int + 1), "k", None)

    assert rig.approvals.approvals == []
    assert rig.notifier.calls == []


def test_a_waiting_run_with_no_pointer_rejects_every_approval() -> None:
    """fail-closed: 상태가 `waiting_approval` 인데 지목 대상이 투영되지 않았다 -- 무엇이 대기 중인지
    모르면 어떤 노드 실행도 대기 중이라고 인정하지 않는다."""
    rig = _Rig()
    view = rig.run()
    rig.project(view.workflow_run_id, WorkflowRunStatus.WAITING_APPROVAL, awaited=None)

    with pytest.raises(NodeExecutionNotWaiting):
        rig.approve(view.workflow_run_id, uuid4(), "k", None)

    assert rig.approvals.approvals == []


def test_approving_twice_is_already_approved_with_one_record_and_one_requeue() -> None:
    """R-8: 두 번 불러도 승인 기록 1건·재큐 1회. 두 번째는 `AlreadyApproved`."""
    rig = _Rig()
    view, awaited = rig.waiting_run()
    rig.approve(view.workflow_run_id, awaited, "k", None)

    with pytest.raises(AlreadyApproved):
        rig.approve(view.workflow_run_id, awaited, "someone-else", "again")

    assert len(rig.approvals.list_for(view.workflow_run_id)) == 1
    assert rig.approvals.approvals[0].approved_by == "k", "첫 승인이 남는다"
    assert len(rig.notifier.calls) == 1


def test_a_repeat_after_the_run_moved_on_is_still_already_approved() -> None:
    """R-8: 실행기가 이미 전진해 Run 이 더는 승인 대기가 아니어도, 같은 노드 실행에 대한 재전송은
    `already_approved` 다 -- "대기 중이 아니다" 로 바뀌면 클라이언트가 재전송 성공을 구별할 수
    없다."""
    rig = _Rig()
    view, awaited = rig.waiting_run()
    rig.approve(view.workflow_run_id, awaited, "k", None)
    rig.project(view.workflow_run_id, WorkflowRunStatus.RUNNING, seq=2)

    with pytest.raises(AlreadyApproved):
        rig.approve(view.workflow_run_id, awaited, "k", None)

    assert len(rig.approvals.approvals) == 1


def test_a_lost_requeue_does_not_undo_or_block_the_approval(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """XADD 실패는 WARNING 만 -- 승인은 기록됐고 실행기는 저장된 사실로 판정하며 재큐가 유실되면
    스위퍼가 줍는다(spec 2.5)."""
    rig = _Rig(notifier=FakeWorkflowRunNotifier(should_fail=True))
    view, awaited = rig.waiting_run()

    with caplog.at_level(logging.WARNING):
        approval = rig.approve(view.workflow_run_id, awaited, "k", None)

    assert rig.approvals.list_for(view.workflow_run_id) == (approval,)
    assert any("workflow_approval.requeue_failed" in r.getMessage() for r in caplog.records)


def test_the_requester_and_a_stranger_are_approved_by_the_same_rule() -> None:
    """**C-4: 권한 모델이 없다.** 인증된 주체 누구나 승인한다 -- 요청자 본인도(자기 승인 금지 없음),
    그 Run 과 아무 관계 없는 주체도. 유스케이스는 "누가 승인할 수 있는가" 를 묻지 않는다."""
    rig = _Rig()
    own, own_awaited = rig.waiting_run()
    stranger_run, stranger_awaited = rig.waiting_run()

    by_requester = rig.approve(own.workflow_run_id, own_awaited, str(_REQUESTER), None)
    by_stranger = rig.approve(stranger_run.workflow_run_id, stranger_awaited, str(uuid4()), None)

    assert by_requester.approved_by == str(_REQUESTER)
    assert by_stranger.approved_by != str(_REQUESTER)
    assert len(rig.approvals.approvals) == 2
