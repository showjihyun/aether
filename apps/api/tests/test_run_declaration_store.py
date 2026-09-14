"""spec 0002 2.1, 2.2, 2.4, 2.10, D-2, D-9, D-11 (P1-5b): `PostgresRunDeclarationStore` —
포트 계약. `aether_control` 역할로 실제 PostgreSQL(`control.runs`) 위에서
create → get, cancel 멱등, `apply_status` 의 `seq` 규칙·`COALESCE`, 없는 run 은
`None`/`RunNotFound` 을 검증합니다.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from uuid import UUID, uuid4

import psycopg
import pytest
from aether_api.adapters.outbound.db.agent_repository import PostgresAgentRepository
from aether_api.adapters.outbound.db.api_keys import PostgresApiKeyStore
from aether_api.adapters.outbound.db.run_declaration_store import PostgresRunDeclarationStore
from aether_api.application.usecases.issue_api_key import IssueApiKeyUseCase
from aether_api.domain.run import RunNotFound, RunView
from aether_runtime.domain.agent import AgentDefinition
from aether_runtime.domain.failure import FailureReason
from aether_runtime.domain.run import RunStatus

pytestmark = pytest.mark.integration


def _agent_version(connect: Callable[[], psycopg.Connection]) -> tuple[UUID, UUID]:
    repo = PostgresAgentRepository(connect)
    definition = AgentDefinition.model_validate({"schema_version": 1, "system_prompt": "x"})
    agent = repo.create(f"run-store-agent-{uuid4()}", definition)
    version = repo.get_version(agent.id, 1)
    return agent.id, version.id


def _requested_by(connect: Callable[[], psycopg.Connection]) -> UUID:
    store = PostgresApiKeyStore(connect)
    issued = IssueApiKeyUseCase(store)(f"run-store-{uuid4()}")
    return issued.key.id


def _get(store: PostgresRunDeclarationStore, run_id: UUID) -> RunView:
    view = store.get(run_id)
    assert view is not None
    return view


def test_create_then_get_returns_the_same_queued_view(
    control_connection_factory: Callable[[], psycopg.Connection],
) -> None:
    connect = control_connection_factory
    store = PostgresRunDeclarationStore(connect)
    agent_id, version_id = _agent_version(connect)
    requested_by = _requested_by(connect)

    created = store.create(agent_id, version_id, 1, "do it", requested_by)
    fetched = _get(store, created.run_id)

    assert fetched == created
    assert fetched.agent_id == agent_id
    assert fetched.agent_version == 1
    assert fetched.status == RunStatus.QUEUED
    assert fetched.requested_by == requested_by
    assert fetched.cancel_requested_at is None


def test_get_missing_run_returns_none(
    control_connection_factory: Callable[[], psycopg.Connection],
) -> None:
    store = PostgresRunDeclarationStore(control_connection_factory)

    assert store.get(uuid4()) is None


def test_request_cancel_is_idempotent(
    control_connection_factory: Callable[[], psycopg.Connection],
) -> None:
    connect = control_connection_factory
    store = PostgresRunDeclarationStore(connect)
    agent_id, version_id = _agent_version(connect)
    requested_by = _requested_by(connect)
    created = store.create(agent_id, version_id, 1, "do it", requested_by)

    first_at = datetime(2026, 1, 1, tzinfo=UTC)
    second_at = datetime(2026, 1, 2, tzinfo=UTC)

    first = store.request_cancel(created.run_id, first_at)
    second = store.request_cancel(created.run_id, second_at)

    assert first.cancel_requested_at == first_at
    assert second.cancel_requested_at == first_at


def test_request_cancel_missing_run_raises_run_not_found(
    control_connection_factory: Callable[[], psycopg.Connection],
) -> None:
    store = PostgresRunDeclarationStore(control_connection_factory)

    with pytest.raises(RunNotFound):
        store.request_cancel(uuid4(), datetime(2026, 1, 1, tzinfo=UTC))


def test_apply_status_seq_rule_and_coalesce(
    control_connection_factory: Callable[[], psycopg.Connection],
) -> None:
    connect = control_connection_factory
    store = PostgresRunDeclarationStore(connect)
    agent_id, version_id = _agent_version(connect)
    requested_by = _requested_by(connect)
    created = store.create(agent_id, version_id, 1, "do it", requested_by)

    started_at = datetime(2026, 1, 1, tzinfo=UTC)
    applied = store.apply_status(
        created.run_id,
        seq=1,
        status=RunStatus.RUNNING,
        started_at=started_at,
        finished_at=None,
        failure_reason=None,
        trace_id="trace-1",
    )
    assert applied is True

    ignored_lower = store.apply_status(
        created.run_id,
        seq=0,
        status=RunStatus.WAITING,
        started_at=None,
        finished_at=None,
        failure_reason=None,
        trace_id=None,
    )
    assert ignored_lower is False

    ignored_same = store.apply_status(
        created.run_id,
        seq=1,
        status=RunStatus.WAITING,
        started_at=None,
        finished_at=None,
        failure_reason=None,
        trace_id=None,
    )
    assert ignored_same is False

    mid_view = _get(store, created.run_id)
    assert mid_view.status == RunStatus.RUNNING  # 낮은/같은 seq 는 반영되지 않았습니다.
    assert mid_view.started_at == started_at
    assert mid_view.trace_id == "trace-1"

    finished_at = datetime(2026, 1, 1, 0, 5, tzinfo=UTC)
    applied_finish = store.apply_status(
        created.run_id,
        seq=2,
        status=RunStatus.FAILED,
        started_at=None,
        finished_at=finished_at,
        failure_reason=FailureReason.MODEL_ERROR,
        trace_id=None,
    )
    assert applied_finish is True

    final_view = _get(store, created.run_id)
    assert final_view.status == RunStatus.FAILED
    assert final_view.started_at == started_at  # None 이 지우지 않습니다(COALESCE).
    assert final_view.finished_at == finished_at
    assert final_view.failure_reason == FailureReason.MODEL_ERROR
    assert final_view.trace_id == "trace-1"  # trace_id=None 이 지우지 않습니다.


def test_apply_status_on_missing_run_returns_false(
    control_connection_factory: Callable[[], psycopg.Connection],
) -> None:
    store = PostgresRunDeclarationStore(control_connection_factory)

    applied = store.apply_status(
        uuid4(),
        seq=1,
        status=RunStatus.RUNNING,
        started_at=None,
        finished_at=None,
        failure_reason=None,
        trace_id=None,
    )

    assert applied is False
