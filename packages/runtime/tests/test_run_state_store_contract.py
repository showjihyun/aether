"""spec 0002 2.1, 2.4, 2.10, D-10: `RunStateStore` 포트 계약 — fake 와 PostgreSQL 이
같은 케이스를 통과합니다(P0-9 `test_api_key_store_contract.py` 와 같은 형태).

`postgres` 케이스는 `data_connection_factory`(`aether_data` 역할, `migrated_database`
로 올라간 세션 DB)를 `PostgresRunStateStore` 의 연결 팩토리로 건넵니다.
`data.run_executions.run_id`·`data.run_states.run_id` 는 `control.runs.id` 의 FK 이므로
(spec 0002 2.10), 먼저 `admin_connection_factory` 로 `control.agents`·`agent_versions`·
`runs`(`input` NOT NULL 포함) 행을 심습니다 — `apps/api/tests/test_plane_roles.py` 의
`_insert_run` 과 같은 절차입니다.

lease 만료를 통한 재획득은 `test_lease.py`(fake, `FakeClock.advance`)가 결정적으로
증명합니다. PostgreSQL 의 lease 는 `now()`(실제 벽시계) 기준이라 대기 없이 만료를
재현할 수 없으므로, 이 계약 테스트는 "만료" 대신 "release 뒤 재획득" 으로 같은 lease
규칙을 두 store 모두에서 검증합니다 — "새 store 인스턴스가 같은 RunState 를 load"
케이스도 여기 있습니다(mvp-backlog P1-2b 완료 판정, 재개의 저장소 절반).
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID

import psycopg
import pytest
from aether_runtime.application.ports.outbound.run_state_store import RunStateStore
from aether_runtime.domain.run import RunState, RunStatus

from packages.runtime.tests.fakes import FakeClock, FakeRunStateStore


class _StoreFactory(Protocol):
    def __call__(self) -> RunStateStore: ...


def _declare_run(admin_connection_factory: Callable[[], psycopg.Connection]) -> UUID:
    """`control.agents` → `agent_versions` → `runs`(`input` 포함) 를 관리자 권한으로 심습니다."""
    conn = admin_connection_factory()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO control.agents (name) VALUES (%s) RETURNING id",
                (f"agent-{uuid.uuid4()}",),
            )
            row = cur.fetchone()
            assert row is not None
            agent_id = row[0]

            cur.execute(
                """
                INSERT INTO control.agent_versions (agent_id, version, definition)
                VALUES (%s, %s, %s)
                RETURNING id
                """,
                (agent_id, 1, json.dumps({"schema_version": 1})),
            )
            row = cur.fetchone()
            assert row is not None
            version_id = row[0]

            cur.execute(
                """
                INSERT INTO control.runs (agent_version_id, input)
                VALUES (%s, %s)
                RETURNING id
                """,
                (version_id, "contract-test-input"),
            )
            row = cur.fetchone()
            assert row is not None
            run_id: UUID = row[0]
        conn.commit()
    finally:
        conn.close()
    return run_id


def _run_id(kind: str, request: pytest.FixtureRequest) -> UUID:
    if kind == "fake":
        return uuid.uuid4()
    admin_factory = request.getfixturevalue("admin_connection_factory")
    return _declare_run(admin_factory)


def _store_factory(kind: str, request: pytest.FixtureRequest) -> _StoreFactory:
    if kind == "fake":
        clock = FakeClock()
        backend = FakeRunStateStore.new_backend()
        return lambda: FakeRunStateStore(clock, backend=backend)

    data_factory: Callable[[], psycopg.Connection] = request.getfixturevalue(
        "data_connection_factory"
    )
    from aether_runtime.adapters.outbound.db.run_state_store import PostgresRunStateStore

    return lambda: PostgresRunStateStore(data_factory)


def _store_kinds() -> list[object]:
    return [
        pytest.param("fake", id="fake"),
        pytest.param("postgres", id="postgres", marks=pytest.mark.integration),
    ]


@pytest.mark.parametrize("store_kind", _store_kinds())
def test_load_returns_none_for_unknown_run(store_kind: str, request: pytest.FixtureRequest) -> None:
    store = _store_factory(store_kind, request)()

    assert store.load(uuid.uuid4()) is None


@pytest.mark.parametrize("store_kind", _store_kinds())
def test_save_then_load_round_trips_state(store_kind: str, request: pytest.FixtureRequest) -> None:
    run_id = _run_id(store_kind, request)
    store = _store_factory(store_kind, request)()
    state = RunState(run_id=run_id, status=RunStatus.RUNNING, step=1, last_seq=3)

    store.save(state)
    loaded = store.load(run_id)

    assert loaded == state


@pytest.mark.parametrize("store_kind", _store_kinds())
def test_new_store_instance_loads_same_state(
    store_kind: str, request: pytest.FixtureRequest
) -> None:
    """재개의 저장소 절반(mvp-backlog P1-2b) — 새 인스턴스가 이전 인스턴스가 저장한
    State 를 봅니다."""
    run_id = _run_id(store_kind, request)
    make_store = _store_factory(store_kind, request)
    state = RunState(run_id=run_id, status=RunStatus.WAITING, step=2, last_seq=7)

    make_store().save(state)
    loaded = make_store().load(run_id)

    assert loaded == state


@pytest.mark.parametrize("store_kind", _store_kinds())
def test_acquire_lease_creates_row_and_succeeds_with_no_prior_lease(
    store_kind: str, request: pytest.FixtureRequest
) -> None:
    run_id = _run_id(store_kind, request)
    store = _store_factory(store_kind, request)()

    acquired = store.acquire_lease(run_id, owner="worker-a", ttl_seconds=60)

    assert acquired is True
    assert store.status(run_id) == RunStatus.QUEUED


@pytest.mark.parametrize("store_kind", _store_kinds())
def test_second_acquire_lease_fails_while_first_is_held(
    store_kind: str, request: pytest.FixtureRequest
) -> None:
    run_id = _run_id(store_kind, request)
    store = _store_factory(store_kind, request)()
    assert store.acquire_lease(run_id, owner="worker-a", ttl_seconds=60) is True

    second = store.acquire_lease(run_id, owner="worker-b", ttl_seconds=60)

    assert second is False


@pytest.mark.parametrize("store_kind", _store_kinds())
def test_release_then_acquire_by_new_owner_succeeds(
    store_kind: str, request: pytest.FixtureRequest
) -> None:
    run_id = _run_id(store_kind, request)
    store = _store_factory(store_kind, request)()
    assert store.acquire_lease(run_id, owner="worker-a", ttl_seconds=60) is True

    store.release(run_id, owner="worker-a")
    acquired = store.acquire_lease(run_id, owner="worker-b", ttl_seconds=60)

    assert acquired is True


@pytest.mark.parametrize("store_kind", _store_kinds())
def test_renew_lease_fails_for_non_owner(store_kind: str, request: pytest.FixtureRequest) -> None:
    run_id = _run_id(store_kind, request)
    store = _store_factory(store_kind, request)()
    assert store.acquire_lease(run_id, owner="worker-a", ttl_seconds=60) is True

    renewed = store.renew_lease(run_id, owner="worker-b", ttl_seconds=60)

    assert renewed is False


@pytest.mark.parametrize("store_kind", _store_kinds())
def test_renew_lease_succeeds_for_owner(store_kind: str, request: pytest.FixtureRequest) -> None:
    run_id = _run_id(store_kind, request)
    store = _store_factory(store_kind, request)()
    assert store.acquire_lease(run_id, owner="worker-a", ttl_seconds=60) is True

    renewed = store.renew_lease(run_id, owner="worker-a", ttl_seconds=60)

    assert renewed is True


@pytest.mark.parametrize("store_kind", _store_kinds())
def test_set_status_then_status_round_trips(
    store_kind: str, request: pytest.FixtureRequest
) -> None:
    run_id = _run_id(store_kind, request)
    store = _store_factory(store_kind, request)()
    store.acquire_lease(run_id, owner="worker-a", ttl_seconds=60)

    store.set_status(run_id, RunStatus.RUNNING)

    assert store.status(run_id) == RunStatus.RUNNING


@pytest.mark.parametrize("store_kind", _store_kinds())
def test_status_returns_none_for_unknown_run(
    store_kind: str, request: pytest.FixtureRequest
) -> None:
    store = _store_factory(store_kind, request)()

    assert store.status(uuid.uuid4()) is None


@pytest.mark.parametrize("store_kind", _store_kinds())
def test_set_status_records_started_at_and_finished_at(
    store_kind: str, request: pytest.FixtureRequest
) -> None:
    """spec 0002 2.4, D-10 (P1-4 순서 1): `ExecuteRun` 의 루프가 재개에 필요한
    `started_at`/`finished_at` 을 `set_status` 로 기록할 수 있어야 합니다 — P1-2b 는
    이 두 인자를 받지 않아 채우지 못했습니다. fake 는 전용 조회 메서드로, PostgreSQL
    은 `data.run_executions` 를 직접 읽어 검증합니다."""
    run_id = _run_id(store_kind, request)
    store = _store_factory(store_kind, request)()
    store.acquire_lease(run_id, owner="worker-a", ttl_seconds=60)
    started = datetime(2026, 1, 1, tzinfo=UTC)
    finished = datetime(2026, 1, 1, 0, 5, tzinfo=UTC)

    store.set_status(run_id, RunStatus.RUNNING, started_at=started)
    store.set_status(run_id, RunStatus.SUCCEEDED, finished_at=finished)

    if store_kind == "fake":
        from packages.runtime.tests.fakes import FakeRunStateStore

        assert isinstance(store, FakeRunStateStore)
        assert store.started_at(run_id) == started
        assert store.finished_at(run_id) == finished
    else:
        data_factory: Callable[[], psycopg.Connection] = request.getfixturevalue(
            "data_connection_factory"
        )
        conn = data_factory()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT started_at, finished_at FROM data.run_executions WHERE run_id = %s",
                    (run_id,),
                )
                row = cur.fetchone()
            conn.rollback()
        finally:
            conn.close()
        assert row is not None
        assert row[0] == started
        assert row[1] == finished


@pytest.mark.parametrize("store_kind", _store_kinds())
def test_set_status_does_not_clobber_started_at_when_omitted(
    store_kind: str, request: pytest.FixtureRequest
) -> None:
    """spec 0002 2.4 (P1-4 순서 1): 루프는 `running -> waiting -> running` 처럼 같은
    Run 에 `set_status` 를 여러 번 부릅니다 — `started_at` 을 주지 않은 호출이 이전에
    기록된 값을 지우면 안 됩니다(PostgreSQL 쪽은 COALESCE, fake 도 같은 규칙)."""
    run_id = _run_id(store_kind, request)
    store = _store_factory(store_kind, request)()
    store.acquire_lease(run_id, owner="worker-a", ttl_seconds=60)
    started = datetime(2026, 1, 1, tzinfo=UTC)

    store.set_status(run_id, RunStatus.RUNNING, started_at=started)
    store.set_status(run_id, RunStatus.WAITING)

    if store_kind == "fake":
        from packages.runtime.tests.fakes import FakeRunStateStore

        assert isinstance(store, FakeRunStateStore)
        assert store.started_at(run_id) == started
    else:
        data_factory = request.getfixturevalue("data_connection_factory")
        conn = data_factory()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT started_at FROM data.run_executions WHERE run_id = %s", (run_id,)
                )
                row = cur.fetchone()
            conn.rollback()
        finally:
            conn.close()
        assert row is not None
        assert row[0] == started


@pytest.mark.integration
def test_postgres_acquire_lease_succeeds_after_lease_until_passed(
    admin_connection_factory: Callable[[], psycopg.Connection],
    data_connection_factory: Callable[[], psycopg.Connection],
) -> None:
    """spec 0002 D-10, R-15: `PostgresRunStateStore` 의 실제 만료 판정을 검증합니다.

    `test_lease.py` 는 `FakeClock.advance()` 로 `FakeRunStateStore` 의 만료 판정을
    증명하지만, 그것은 fake 의 파이썬 비교 로직만 증명할 뿐 `PostgresRunStateStore`
    의 SQL 조건(`lease_until IS NULL OR lease_until < now()`)이 실제 DB 에서 맞게
    동작하는지는 증명하지 못합니다 — 그 줄이 틀려도(예: 부등호가 뒤집혀도) 지금까지의
    계약 테스트는 통과합니다. 이 테스트는 관리자 접속으로 `lease_until` 을 과거로
    되돌려 심어(`apps/api/tests/test_api_key_store_contract.py` 가 `revoked_at` 을
    한 시간 전으로 되돌려 심는 것과 같은 방식) `sleep` 없이 만료를 재현합니다.

    경계는 `<`(미만)이지 `<=`(이하)가 아닙니다 — `lease_until == now()` 인 순간에는
    그 worker 가 여전히 lease 를 쥔 것으로 취급해, 방금 발급된 lease 를 같은 순간의
    다른 트랜잭션이 곧바로 빼앗지 못하게 하는 여유입니다. 그래서 이 테스트는
    `now() - interval '1 second'` 로 확실히 과거를 심어 그 경계와 무관하게 만료를
    재현합니다.
    """
    from aether_runtime.adapters.outbound.db.run_state_store import PostgresRunStateStore

    run_id = _declare_run(admin_connection_factory)
    store = PostgresRunStateStore(data_connection_factory)

    assert store.acquire_lease(run_id, owner="worker-a", ttl_seconds=60) is True
    assert store.acquire_lease(run_id, owner="worker-b", ttl_seconds=60) is False

    admin_conn = admin_connection_factory()
    try:
        with admin_conn.cursor() as cur:
            cur.execute(
                """
                UPDATE data.run_executions
                SET lease_until = now() - interval '1 second'
                WHERE run_id = %s
                """,
                (run_id,),
            )
        admin_conn.commit()
    finally:
        admin_conn.close()

    acquired = store.acquire_lease(run_id, owner="worker-b", ttl_seconds=60)
    assert acquired is True

    data_conn = data_connection_factory()
    try:
        with data_conn.cursor() as cur:
            cur.execute(
                "SELECT lease_owner FROM data.run_executions WHERE run_id = %s",
                (run_id,),
            )
            row = cur.fetchone()
        data_conn.rollback()
    finally:
        data_conn.close()

    assert row is not None
    assert row[0] == "worker-b"
