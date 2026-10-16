"""spec 0005 2.9 개정 2, R-6, R-8: `WorkflowRunStateStore` 포트 계약 - fake 와 PostgreSQL 이 같은
케이스를 통과합니다(`test_run_state_store_contract.py` 와 같은 형태).

`postgres` 케이스는 `data_connection_factory`(`aether_data` 역할)를 연결 팩토리로 건넵니다.
`data.workflow_run_executions.workflow_run_id` 는 `control.workflow_runs.id` 의 FK 이므로
`tests/support/workflow_db.py` 로 먼저 선언을 심습니다.

PostgreSQL 의 lease 는 `now()`(실제 벽시계) 기준이라 대기 없이 만료를 재현할 수 없으므로
"만료" 대신 "release 뒤 재획득" 으로 같은 규칙을 두 store 모두에서 검증합니다.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID, uuid4

import psycopg
import pytest
from aether_workflow.adapters.outbound.db.workflow_run_state_store import (
    PostgresWorkflowRunStateStore,
)
from aether_workflow.application.ports.outbound.workflow_run_state_store import (
    WorkflowRunStateStore,
)
from aether_workflow.domain.failure import WorkflowFailureReason
from aether_workflow.domain.node import Edge, Node, NodeKind
from aether_workflow.domain.node_execution import NodeExecutionStatus
from aether_workflow.domain.node_output import NodeOutput
from aether_workflow.domain.run_status import WorkflowRunStatus

from packages.workflow.tests.fakes import FakeWorkflowRunStateStore
from tests.support.workflow_db import declare_workflow_run

_NOW = datetime(2026, 10, 14, 12, 0, tzinfo=UTC)


class _Factory(Protocol):
    def __call__(self) -> tuple[WorkflowRunStateStore, UUID]: ...


@pytest.fixture(params=["fake", pytest.param("postgres", marks=pytest.mark.integration)])
def make(
    request: pytest.FixtureRequest,
) -> _Factory:
    if request.param == "fake":

        def _fake() -> tuple[WorkflowRunStateStore, UUID]:
            return FakeWorkflowRunStateStore(), uuid4()

        return _fake

    admin: Callable[[], psycopg.Connection] = request.getfixturevalue("admin_connection_factory")
    data: Callable[[], psycopg.Connection] = request.getfixturevalue("data_connection_factory")

    def _postgres() -> tuple[WorkflowRunStateStore, UUID]:
        run_id, _ = declare_workflow_run(
            admin,
            (Node("start", NodeKind.START), Node("end", NodeKind.END)),
            (Edge("start", "end"),),
        )
        return PostgresWorkflowRunStateStore(data), run_id

    return _postgres


def test_load_is_none_before_the_first_lease(make: _Factory) -> None:
    store, run_id = make()
    assert store.load(run_id) is None


def test_first_acquire_creates_a_queued_row_and_a_second_owner_is_refused(make: _Factory) -> None:
    """spec 0005 2.9: 행이 없으면 `queued` 로 만들고 잡는다 - 쥔 lease 는 못 잡는다."""
    store, run_id = make()

    assert store.acquire_lease(run_id, "a", 60.0) is True
    execution = store.load(run_id)
    assert execution is not None
    assert execution.status is WorkflowRunStatus.QUEUED
    assert execution.status_seq == 0
    assert execution.current_node_id is None
    assert store.acquire_lease(run_id, "b", 60.0) is False


def test_release_by_a_non_owner_keeps_the_lease_and_release_by_the_owner_frees_it(
    make: _Factory,
) -> None:
    store, run_id = make()
    store.acquire_lease(run_id, "a", 60.0)

    store.release(run_id, "b")
    assert store.acquire_lease(run_id, "c", 60.0) is False

    store.release(run_id, "a")
    assert store.acquire_lease(run_id, "c", 60.0) is True


def test_renew_succeeds_only_for_the_owner(make: _Factory) -> None:
    store, run_id = make()
    store.acquire_lease(run_id, "a", 60.0)

    assert store.renew_lease(run_id, "a", 60.0) is True
    assert store.renew_lease(run_id, "b", 60.0) is False


def test_set_status_persists_seq_and_does_not_erase_earlier_optional_values(
    make: _Factory,
) -> None:
    """COALESCE 의미: 주지 않은 호출이 이전의 `started_at`·`current_node_id` 를 지우지 않는다."""
    store, run_id = make()
    store.acquire_lease(run_id, "a", 60.0)

    store.set_status(
        run_id, WorkflowRunStatus.RUNNING, seq=1, current_node_id="start", started_at=_NOW
    )
    store.set_status(run_id, WorkflowRunStatus.RUNNING, seq=2)
    store.set_status(
        run_id,
        WorkflowRunStatus.FAILED,
        seq=3,
        failure_reason=WorkflowFailureReason.UNSUPPORTED_NODE_KIND,
        finished_at=_NOW,
    )

    execution = store.load(run_id)
    assert execution is not None
    assert execution.status is WorkflowRunStatus.FAILED
    assert execution.status_seq == 3
    assert execution.current_node_id == "start"
    assert execution.started_at == _NOW
    assert execution.finished_at == _NOW
    assert execution.failure_reason == "unsupported_node_kind"


def test_start_node_returns_none_when_already_recorded(make: _Factory) -> None:
    """spec 0005 R-8: `None` 은 "이미 기록돼 있다" - 노드당 한 행."""
    store, run_id = make()
    store.acquire_lease(run_id, "a", 60.0)

    first = store.start_node(run_id, "start", 0)
    second = store.start_node(run_id, "start", 0)
    other_iteration = store.start_node(run_id, "start", 1)

    assert first is not None
    assert second is None
    assert other_iteration is not None
    assert [(r.node_id, r.iteration) for r in store.node_executions(run_id)] == [
        ("start", 0),
        ("start", 1),
    ]


def test_finish_node_records_status_and_time(make: _Factory) -> None:
    store, run_id = make()
    store.acquire_lease(run_id, "a", 60.0)
    node_execution_id = store.start_node(run_id, "start", 0)
    assert node_execution_id is not None

    store.finish_node(node_execution_id, NodeExecutionStatus.SUCCEEDED, _NOW)

    (record,) = store.node_executions(run_id)
    assert record.id == node_execution_id
    assert record.workflow_run_id == run_id
    assert record.status is NodeExecutionStatus.SUCCEEDED
    assert record.finished_at == _NOW


def test_park_node_persists_the_child_id_and_waiting_status_in_one_step(make: _Factory) -> None:
    """spec 0005 R-8 (B2): 자식 Run 의 id 와 `waiting_run` 은 한 문장으로 영속된다 - 발사 전에
    부른다.
    그 뒤 같은 노드를 다시 시작하면 `None` 이고, 읽으면 같은 id 가 돌아온다."""
    store, run_id = make()
    store.acquire_lease(run_id, "a", 60.0)
    node_execution_id = store.start_node(run_id, "agent", 0)
    assert node_execution_id is not None
    child = uuid4()

    store.park_node(node_execution_id, child)

    (record,) = store.node_executions(run_id)
    assert record.status is NodeExecutionStatus.WAITING_RUN
    assert record.agent_run_id == child
    assert record.finished_at is None
    assert store.start_node(run_id, "agent", 0) is None


def test_finish_node_records_the_failure_reason(make: _Factory) -> None:
    """B2: 노드가 실패한 사유가 남는다 - Workflow 를 끝내기 전에 죽은 재개가 같은 사유로 끝낸다."""
    store, run_id = make()
    store.acquire_lease(run_id, "a", 60.0)
    node_execution_id = store.start_node(run_id, "agent", 0)
    assert node_execution_id is not None

    store.finish_node(
        node_execution_id,
        NodeExecutionStatus.FAILED,
        _NOW,
        WorkflowFailureReason.AGENT_VERSION_NOT_FOUND,
    )

    (record,) = store.node_executions(run_id)
    assert record.status is NodeExecutionStatus.FAILED
    assert record.failure_reason == "agent_version_not_found"
    assert record.agent_run_id is None


def test_waiting_run_id_exists_only_while_the_status_is_waiting_run(make: _Factory) -> None:
    """B2: `waiting_run_id` 는 상태에서 유도된다(api 의 투영 불변식과 같다) - `waiting_run` 일 때만
    값이 있고, 주지 않은 `waiting_run` 호출은 이전 값을 지우지 않으며, 다른 상태로 가면 지워진다.
    그리고 R-7 의 근거: 파킹은 lease 열을 건드리지 않는다."""
    store, run_id = make()
    store.acquire_lease(run_id, "a", 60.0)
    child = uuid4()

    store.set_status(run_id, WorkflowRunStatus.RUNNING, seq=1)
    store.set_status(run_id, WorkflowRunStatus.WAITING_RUN, seq=2, waiting_run_id=child)
    parked = store.load(run_id)
    store.set_status(run_id, WorkflowRunStatus.WAITING_RUN, seq=3)
    still = store.load(run_id)
    store.release(run_id, "a")
    store.set_status(run_id, WorkflowRunStatus.RUNNING, seq=4)
    resumed = store.load(run_id)

    assert parked is not None and still is not None and resumed is not None
    assert parked.status is WorkflowRunStatus.WAITING_RUN
    assert parked.waiting_run_id == child
    assert still.waiting_run_id == child
    assert resumed.waiting_run_id is None
    assert store.acquire_lease(run_id, "b", 60.0) is True, "release 뒤에는 누구든 다시 잡는다"


def test_park_node_for_approval_marks_only_the_node_as_waiting_approval(make: _Factory) -> None:
    """spec 0005 2.6 개정 5, R-12 (P4-4): 승인은 노드 실행을 **지목**하므로 행은 `start_node` 가
    이미
    만들었고, 파킹은 상태만 `waiting_approval` 로 바꾼다 - 자식 Run 의 id 는 없다. 같은 노드를 다시
    시작하면 `None` 이다(멱등)."""
    store, run_id = make()
    store.acquire_lease(run_id, "a", 60.0)
    node_execution_id = store.start_node(run_id, "gate", 0)
    assert node_execution_id is not None

    store.park_node_for_approval(node_execution_id)

    (record,) = store.node_executions(run_id)
    assert record.id == node_execution_id
    assert record.status is NodeExecutionStatus.WAITING_APPROVAL
    assert record.agent_run_id is None
    assert record.finished_at is None
    assert store.start_node(run_id, "gate", 0) is None


def test_waiting_node_execution_id_exists_only_while_the_status_is_waiting_approval(
    make: _Factory,
) -> None:
    """spec 0005 2.6 개정 5 (1) (P4-4): 지목 대상은 `waiting_run_id` 와 같은 불변식 - 상태에서
    유도된다. `waiting_approval` 일 때만 값이 있고, 주지 않은 `waiting_approval` 호출은 이전 값을
    지우지 않으며, 다른 상태(`running`)로 가면 지워진다. 대기 중에도 lease 열은 건드리지 않는다."""
    store, run_id = make()
    store.acquire_lease(run_id, "a", 60.0)
    node_execution_id = store.start_node(run_id, "gate", 0)
    assert node_execution_id is not None

    store.set_status(run_id, WorkflowRunStatus.RUNNING, seq=1)
    store.set_status(
        run_id,
        WorkflowRunStatus.WAITING_APPROVAL,
        seq=2,
        current_node_id="gate",
        waiting_node_execution_id=node_execution_id,
    )
    parked = store.load(run_id)
    store.set_status(run_id, WorkflowRunStatus.WAITING_APPROVAL, seq=3)
    still = store.load(run_id)
    store.release(run_id, "a")
    store.set_status(run_id, WorkflowRunStatus.RUNNING, seq=4)
    resumed = store.load(run_id)

    assert parked is not None and still is not None and resumed is not None
    assert parked.status is WorkflowRunStatus.WAITING_APPROVAL
    assert parked.waiting_node_execution_id == node_execution_id
    assert parked.waiting_run_id is None
    assert still.waiting_node_execution_id == node_execution_id
    assert resumed.waiting_node_execution_id is None
    assert store.acquire_lease(run_id, "b", 60.0) is True, "release 뒤에는 누구든 다시 잡는다"


def test_finish_node_without_output_leaves_the_output_empty(make: _Factory) -> None:
    """spec 0005 2.4 개정 4: 출력이 없는 노드(`START`·`END`·`CONDITION`)는 `NULL` 이다 - 빈 객체가
    아니다."""
    store, run_id = make()
    store.acquire_lease(run_id, "a", 60.0)
    node_execution_id = store.start_node(run_id, "start", 0)
    assert node_execution_id is not None

    store.finish_node(node_execution_id, NodeExecutionStatus.SUCCEEDED, _NOW)

    (record,) = store.node_executions(run_id)
    assert record.output is None
    assert record.output_truncated is False


@pytest.mark.parametrize("truncated", [False, True])
def test_finish_node_records_the_output_and_the_truncation_flag_together(
    make: _Factory, truncated: bool
) -> None:
    """spec 0005 2.4 개정 4 (4): 값과 잘렸다는 사실은 한 번에 적힌다. 한국어가 그대로 돌아온다."""
    store, run_id = make()
    store.acquire_lease(run_id, "a", 60.0)
    node_execution_id = store.start_node(run_id, "ask", 0)
    assert node_execution_id is not None
    value = {"text": "안녕하세요", "status": "succeeded"}

    store.finish_node(
        node_execution_id,
        NodeExecutionStatus.SUCCEEDED,
        _NOW,
        output=NodeOutput(value, truncated=truncated),
    )

    (record,) = store.node_executions(run_id)
    assert record.output == value
    assert record.output_truncated is truncated
