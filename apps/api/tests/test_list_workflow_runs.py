"""spec 0006 2.3, D-3: `ListWorkflowRunsUseCase` - 투영의 커서 페이지와 상태 필터를 전달합니다."""

from __future__ import annotations

from uuid import uuid4

from aether_api.application.usecases.list_workflow_runs import ListWorkflowRunsUseCase
from aether_workflow.domain.node import Edge, Node, NodeKind
from aether_workflow.domain.run_status import WorkflowRunStatus

from apps.api.tests.fakes_workflow import FakeWorkflowRepository, FakeWorkflowRunDeclarationStore


def test_list_workflow_runs_pages_and_filters_by_status() -> None:
    """spec 0006 2.3: 상태 필터는 그 상태만, 커서는 다음 쪽을 잇는다."""
    repo = FakeWorkflowRepository()
    store = FakeWorkflowRunDeclarationStore(repo)
    workflow_id = repo.create(
        "wf", (Node("s", NodeKind.START), Node("e", NodeKind.END)), (Edge("s", "e"),)
    ).id
    runs = [store.create(workflow_id, 1, None, uuid4()) for _ in range(3)]
    store.apply_status(
        runs[0].workflow_run_id,
        seq=1,
        status=WorkflowRunStatus.RUNNING,
        current_node_id=None,
        waiting_run_id=None,
        started_at=None,
        finished_at=None,
        failure_reason=None,
    )
    list_runs = ListWorkflowRunsUseCase(store)

    page1 = list_runs(2, None, None)
    page2 = list_runs(2, page1.next_cursor, None)
    only_running = list_runs(50, None, WorkflowRunStatus.RUNNING)

    assert len(page1.items) == 2 and page1.next_cursor is not None
    assert len(page2.items) == 1 and page2.next_cursor is None
    assert [r.workflow_run_id for r in only_running.items] == [runs[0].workflow_run_id]
