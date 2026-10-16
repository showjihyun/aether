"""spec 0005 2.5 개정 8 (2), R-7 (P4-3 둘째 물결): 파킹은 **상태 저장 -> lease 해제 -> 이벤트·통지**
순서다 - fake 저장소에 호출 순서를 기록해 고정한다(컨테이너 없이, AR-9).

왜 순서가 문제인가: 이벤트·통지를 낸 뒤 `finally` 에서 lease 를 놓으면, 관찰자(투영을 읽는 api,
이벤트를 구독하는 쪽)가 "상태는 대기인데 lease 는 아직 잡힌" 창을 실제로 본다(전량 통합 3회 중
2회에서
승인 파킹의 lease 단언이 흔들렸다). 세 파킹 경로(`waiting_run`·`waiting_approval`·`waiting_timer`)
각각에 적용하고, 종결(`_finish`)은 지금 순서 그대로다.
"""

from __future__ import annotations

from uuid import UUID

import pytest
from aether_workflow.application.usecases.advance_workflow_run import AdvanceWorkflowRunUseCase
from aether_workflow.domain.node import Edge, Node, NodeKind
from aether_workflow.domain.run_status import WorkflowRunStatus

from packages.workflow.tests.fakes import (
    FakeAgentRunLauncher,
    FakeAgentRunReader,
    FakeApprovalReader,
    FakeWorkflowClock,
    FakeWorkflowRunDeclarationReader,
    FakeWorkflowRunStateStore,
    LoggingWorkflowEventSink,
    LoggingWorkflowStatusNotifier,
)

_AGENT = UUID("00000000-0000-0000-0000-0000000000a1")

_PARKINGS = [
    pytest.param(Node("n", NodeKind.AGENT, agent_id=_AGENT), "waiting_run", id="waiting_run"),
    pytest.param(Node("n", NodeKind.HUMAN), "waiting_approval", id="waiting_approval-human"),
    pytest.param(Node("n", NodeKind.APPROVAL), "waiting_approval", id="waiting_approval-approval"),
    pytest.param(Node("n", NodeKind.WAIT, wait_seconds=60), "waiting_timer", id="waiting_timer"),
]


def _advance_once(node: Node) -> tuple[FakeWorkflowRunStateStore, WorkflowRunStatus]:
    store = FakeWorkflowRunStateStore()
    reader = FakeWorkflowRunDeclarationReader()
    agent_runs = FakeAgentRunReader()
    agent_runs.add_version(_AGENT, None)
    advance = AdvanceWorkflowRunUseCase(
        store,
        reader,
        LoggingWorkflowEventSink(store.call_log),
        LoggingWorkflowStatusNotifier(store.call_log),
        FakeWorkflowClock(),
        agent_runs=agent_runs,
        approvals=FakeApprovalReader(),
        launcher=FakeAgentRunLauncher(store),
        owner="worker-a",
        lease_ttl_seconds=60.0,
    )
    run_id = reader.add(
        (Node("start", NodeKind.START), node, Node("end", NodeKind.END)),
        (Edge("start", "n"), Edge("n", "end")),
    )
    return store, advance(run_id)


@pytest.mark.parametrize(("node", "parked"), _PARKINGS)
def test_a_parking_saves_the_state_then_releases_the_lease_then_publishes_and_notifies(
    node: Node, parked: str
) -> None:
    """개정 8 (2): 상태 저장 < `release` < `publish`·`notify`. `finally` 의 `release` 는 그대로라 한
    번 더 불린다(같은 owner 조건부 UPDATE 라 무해)."""
    store, status = _advance_once(node)

    assert status.value == parked
    log = store.call_log
    release = log.index("release")
    last_save = max(i for i, entry in enumerate(log) if entry == f"set_status:{parked}")
    assert last_save < release, log
    assert release < log.index(f"publish:workflow.status:{parked}"), log
    assert release < log.index(f"notify:{parked}"), log
    if parked == "waiting_approval":
        assert release < log.index("publish:approval.requested"), log
    assert log.count("release") == 2, "finally 의 release 는 그대로다(멱등)"


def test_the_lease_is_already_free_when_the_parking_is_announced() -> None:
    """관찰 가능한 결과: 대기 상태가 발행되는 시점에 lease 는 이미 풀려 있다 - "상태는 대기인데
    lease 는 잡힌" 창이 없다."""
    store = FakeWorkflowRunStateStore()
    observed: list[str | None] = []
    run_holder: list[UUID] = []

    class _ObservingSink(LoggingWorkflowEventSink):
        def publish(self, event):  # type: ignore[no-untyped-def]
            if (
                event.type == "workflow.status"
                and event.payload.get("status") == "waiting_approval"
            ):
                observed.append(store.lease_owner[run_holder[0]])
            super().publish(event)

    reader = FakeWorkflowRunDeclarationReader()
    advance = AdvanceWorkflowRunUseCase(
        store,
        reader,
        _ObservingSink(store.call_log),
        LoggingWorkflowStatusNotifier(store.call_log),
        FakeWorkflowClock(),
        agent_runs=FakeAgentRunReader(),
        approvals=FakeApprovalReader(),
        launcher=FakeAgentRunLauncher(store),
        owner="worker-a",
        lease_ttl_seconds=60.0,
    )
    run_id = reader.add(
        (Node("start", NodeKind.START), Node("n", NodeKind.HUMAN), Node("end", NodeKind.END)),
        (Edge("start", "n"), Edge("n", "end")),
    )
    run_holder.append(run_id)

    advance(run_id)

    assert observed == [None]


def test_the_terminal_order_is_unchanged() -> None:
    """종결(`_finish`)은 지금 순서 그대로: 종결 한 쌍을 먼저 내고 종결 상태를 마지막에 저장하며,
    lease 는 끝의 `finally` 하나뿐이다."""
    store = FakeWorkflowRunStateStore()
    reader = FakeWorkflowRunDeclarationReader()
    advance = AdvanceWorkflowRunUseCase(
        store,
        reader,
        LoggingWorkflowEventSink(store.call_log),
        LoggingWorkflowStatusNotifier(store.call_log),
        FakeWorkflowClock(),
        agent_runs=FakeAgentRunReader(),
        approvals=FakeApprovalReader(),
        launcher=FakeAgentRunLauncher(store),
        owner="worker-a",
        lease_ttl_seconds=60.0,
    )
    run_id = reader.add(
        (Node("start", NodeKind.START), Node("end", NodeKind.END)), (Edge("start", "end"),)
    )

    assert advance(run_id) is WorkflowRunStatus.SUCCEEDED

    log = store.call_log
    assert log.index("publish:workflow.finished:succeeded") < log.index("set_status:succeeded")
    assert log.count("release") == 1
    assert log[-1] == "release"
