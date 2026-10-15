"""spec 0005 2.6 개정 5, R-8, R-12 (P4-4): `WorkflowApprovalStore` 포트 계약 -- fake 와 PostgreSQL
이
같은 케이스를 통과합니다(`test_api_key_store_contract.py` 와 같은 형태).

증명하는 것: 기록한 승인이 `get`/`list_for` 로 읽힌다 / **같은 `(run, node_execution)` 을 두 번
기록하면 `AlreadyApproved` 이고 기록은 1건** (PostgreSQL 에서는 `unique` 제약이 판정한다) / 다른
노드
실행의 승인은 같은 Run 에 들어간다 / `approved_by` 는 건넨 문자열 그대로다.

`postgres` 케이스는 `control_connection_factory`(`aether_control` 역할 - 운영에서 api 가 쓰는
역할)로
접속하고, FK 를 만족시킬 Workflow Run 은 관리자 역할로 먼저 심습니다.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from typing import Protocol

import psycopg
import pytest
from aether_api.adapters.outbound.db.workflow_approval_store import PostgresWorkflowApprovalStore
from aether_api.application.ports.outbound.workflow_approval_store import WorkflowApprovalStore
from aether_api.domain.workflow_approval import AlreadyApproved
from aether_workflow.domain.node import Edge, Node, NodeKind

from apps.api.tests.fakes_workflow import FakeWorkflowApprovalStore
from tests.support.workflow_db import declare_workflow_run


class _Factory(Protocol):
    def __call__(self) -> tuple[WorkflowApprovalStore, uuid.UUID]: ...


@pytest.fixture(params=["fake", pytest.param("postgres", marks=pytest.mark.integration)])
def make(request: pytest.FixtureRequest) -> _Factory:
    if request.param == "fake":

        def _fake() -> tuple[WorkflowApprovalStore, uuid.UUID]:
            return FakeWorkflowApprovalStore(), uuid.uuid4()

        return _fake

    admin: Callable[[], psycopg.Connection] = request.getfixturevalue("admin_connection_factory")
    control: Callable[[], psycopg.Connection] = request.getfixturevalue(
        "control_connection_factory"
    )

    def _postgres() -> tuple[WorkflowApprovalStore, uuid.UUID]:
        run_id, _ = declare_workflow_run(
            admin,
            (Node("s", NodeKind.START), Node("e", NodeKind.END)),
            (Edge("s", "e"),),
        )
        return PostgresWorkflowApprovalStore(control), run_id

    return _postgres


def test_a_recorded_approval_is_read_back_exactly_as_given(make: _Factory) -> None:
    store, run_id = make()
    node_execution_id = uuid.uuid4()

    recorded = store.record(run_id, node_execution_id, "principal-id-1", "ok")

    assert recorded.workflow_run_id == run_id
    assert recorded.node_execution_id == node_execution_id
    assert recorded.approved_by == "principal-id-1", "건넨 주체 id 를 그대로 적는다"
    assert recorded.note == "ok"
    assert recorded.approved_at is not None
    assert store.get(run_id, node_execution_id) == recorded
    assert store.list_for(run_id) == (recorded,)


def test_get_is_none_for_a_node_execution_without_an_approval(make: _Factory) -> None:
    store, run_id = make()
    store.record(run_id, uuid.uuid4(), "p", None)

    assert store.get(run_id, uuid.uuid4()) is None
    assert store.get(uuid.uuid4(), uuid.uuid4()) is None


def test_the_note_is_optional(make: _Factory) -> None:
    store, run_id = make()

    assert store.record(run_id, uuid.uuid4(), "p", None).note is None


def test_approving_the_same_node_execution_twice_is_already_approved_and_keeps_one_record(
    make: _Factory,
) -> None:
    """R-8: 승인은 노드 실행당 한 건 - 두 번째는 `AlreadyApproved`, 첫 기록이 그대로 남는다."""
    store, run_id = make()
    node_execution_id = uuid.uuid4()
    first = store.record(run_id, node_execution_id, "first", "n1")

    with pytest.raises(AlreadyApproved):
        store.record(run_id, node_execution_id, "second", "n2")

    assert store.list_for(run_id) == (first,)
    assert store.get(run_id, node_execution_id) == first


def test_other_node_executions_of_the_same_run_are_approved_independently(make: _Factory) -> None:
    store, run_id = make()
    a, b = uuid.uuid4(), uuid.uuid4()

    store.record(run_id, a, "p", None)
    store.record(run_id, b, "p", None)

    assert {x.node_execution_id for x in store.list_for(run_id)} == {a, b}


def test_list_for_returns_only_that_runs_approvals(make: _Factory) -> None:
    store, run_id = make()
    store.record(run_id, uuid.uuid4(), "p", None)

    assert store.list_for(uuid.uuid4()) == ()
