"""spec 0005 2.9 개정 2, 2.3, D-5 (P4-2a A1): 마이그레이션 0006 `data.workflow_run_executions` 와
`control.workflow_runs` 투영의 PostgreSQL 구현 — 실제 PostgreSQL.

`api-integration`. 0006 up/down 왕복, `status` 열이 `control.workflow_run_status` 를
재사용(새 enum 없음)하고 `aether_data` 가 실제로 쓸 수 있음, GRANT 경계(`aether_data` 전부 /
`aether_control` 없음 / `control.workflow_runs` 는 여전히 SELECT 뿐 — 개정 2 가 GRANT 를
넓히지 않은 증거), 투영 `apply_status` 의 단조 증가와 `COALESCE`.

GRANT 단언은 **두 겹**입니다. 동작(권한 부족 예외)은 스키마 `data` 에 USAGE 가 없는 것(0001
R-7)으로도 막히므로 표 GRANT 한 줄의 유무를 가리지 못합니다. 그래서 `has_table_privilege`
(표 ACL 만 봅니다)를 함께 단언해 GRANT 한 줄이 실제로 단언을 발화시키게 합니다.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

import psycopg
import pytest
from aether_api.adapters.outbound.db.workflow_repository import PostgresWorkflowRepository
from aether_api.adapters.outbound.db.workflow_run_declaration_store import (
    PostgresWorkflowRunDeclarationStore,
)
from aether_api.domain.workflow import WorkflowVersionNotFound
from aether_workflow.domain.node import Edge, Node, NodeKind
from aether_workflow.domain.run_status import WorkflowRunStatus
from alembic import command
from alembic.config import Config

pytestmark = pytest.mark.integration

_Factory = Callable[[], psycopg.Connection]
_TABLE = "data.workflow_run_executions"
_EXPECTED_COLUMNS = {
    "workflow_run_id",
    "status",
    "status_seq",
    "current_node_id",
    "waiting_run_id",
    "lease_owner",
    "lease_until",
    "started_at",
    "finished_at",
    "failure_reason",
    "updated_at",
}


def _issue_key(connect: _Factory) -> uuid.UUID:
    """`control.workflow_runs.requested_by` FK 를 만족시키는 실제 api key (0007)."""
    from aether_api.adapters.outbound.db.api_keys import PostgresApiKeyStore
    from aether_api.application.usecases.issue_api_key import IssueApiKeyUseCase

    return IssueApiKeyUseCase(PostgresApiKeyStore(connect))(f"k-{uuid.uuid4()}").key.id


def _seed_workflow_run(connect: _Factory) -> uuid.UUID:
    """`aether_control` 의 저장소로 Workflow → Version 1 → Run 선언을 만들고 run id 를 돌려준다."""
    repository = PostgresWorkflowRepository(connect)
    view = repository.create(
        f"wf-{uuid.uuid4()}",
        (Node("s", NodeKind.START), Node("e", NodeKind.END)),
        (Edge("s", "e"),),
    )
    store = PostgresWorkflowRunDeclarationStore(connect)
    return store.create(view.id, 1, None, _issue_key(connect)).workflow_run_id


def _has_privilege(conn: psycopg.Connection, role: str, table: str, privilege: str) -> bool:
    with conn.cursor() as cur:
        cur.execute("SELECT has_table_privilege(%s, %s, %s)", (role, table, privilege))
        row = cur.fetchone()
    assert row is not None
    return bool(row[0])


# --- 마이그레이션 ---------------------------------------------------------------


def test_0006_downgrade_then_upgrade_round_trip(
    alembic_config: Config, admin_connection_factory: _Factory
) -> None:
    """spec 0005 2.9 개정 2: 0006 up → down → up. 되돌리면 표만 사라지고 0005 의 표와 enum 은
    그대로이며, 다시 올리면 표와 열 전부가 돌아온다."""
    command.upgrade(alembic_config, "head")
    command.downgrade(alembic_config, "0005")

    conn = admin_connection_factory()
    try:
        assert not _table_exists(conn)
        assert _table_exists(conn, "control", "workflow_runs")
        assert _enum_exists(conn)
    finally:
        conn.close()

    command.upgrade(alembic_config, "head")

    conn = admin_connection_factory()
    try:
        assert _table_exists(conn)
        with conn.cursor() as cur:
            cur.execute(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema = 'data' AND table_name = 'workflow_run_executions'"
            )
            assert {r[0] for r in cur.fetchall()} == _EXPECTED_COLUMNS
    finally:
        conn.close()


def _table_exists(
    conn: psycopg.Connection, schema: str = "data", name: str = "workflow_run_executions"
) -> bool:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT 1 FROM information_schema.tables WHERE table_schema = %s AND table_name = %s",
            (schema, name),
        )
        return cur.fetchone() is not None


def _enum_exists(conn: psycopg.Connection) -> bool:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT 1 FROM pg_type t JOIN pg_namespace n ON n.oid = t.typnamespace "
            "WHERE n.nspname = 'control' AND t.typname = 'workflow_run_status'"
        )
        return cur.fetchone() is not None


# --- status 열: enum 재사용 --------------------------------------------------------


def test_status_column_reuses_control_enum_and_no_new_enum_exists(
    admin_connection_factory: _Factory,
) -> None:
    """spec 0005 2.9 개정 2: `status` 의 타입은 `control.workflow_run_status` 이고, 0006 이 enum 을
    새로 만들지 않았다(전체 enum 타입 중 `workflow` 가 들어간 것은 그 하나뿐)."""
    conn = admin_connection_factory()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT udt_schema, udt_name FROM information_schema.columns "
                "WHERE table_schema = 'data' AND table_name = 'workflow_run_executions' "
                "AND column_name = 'status'"
            )
            assert cur.fetchone() == ("control", "workflow_run_status")
            cur.execute(
                "SELECT n.nspname, t.typname FROM pg_type t "
                "JOIN pg_namespace n ON n.oid = t.typnamespace "
                "WHERE t.typtype = 'e' AND t.typname LIKE '%workflow%'"
            )
            # 0006 은 새 enum 을 만들지 않았다. 목록에 있는 둘째는 0007 이 노드 실행 상태를 좁히며
            # 만든 것이다(`data.workflow_node_execution_status`, Workflow Run 의 것과 다른 타입).
            assert sorted(cur.fetchall()) == [
                ("control", "workflow_run_status"),
                ("data", "workflow_node_execution_status"),
            ]
    finally:
        conn.close()


def test_data_role_stores_every_enum_value_and_rejects_unknown_ones(
    control_connection_factory: _Factory, data_connection_factory: _Factory
) -> None:
    """spec 0005 2.9 개정 2: `aether_data` 가 `control` 의 enum 을 컬럼 타입으로 실제로 쓸 수 있고
    (스키마 USAGE), 값 일곱 개가 들어가며, 정의에 없는 값은 거부된다(`timed_out` 은 Agent Run
    의 것)."""
    run_id = _seed_workflow_run(control_connection_factory)
    conn = data_connection_factory()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO data.workflow_run_executions (workflow_run_id) VALUES (%s) "
                "RETURNING status, status_seq, lease_owner",
                (run_id,),
            )
            assert cur.fetchone() == ("queued", 0, None)
            for value in (
                "running",
                "waiting_run",
                "waiting_approval",
                "succeeded",
                "failed",
                "cancelled",
                "queued",
            ):
                cur.execute(
                    "UPDATE data.workflow_run_executions SET status = %s "
                    "WHERE workflow_run_id = %s RETURNING status::text",
                    (value, run_id),
                )
                assert cur.fetchone() == (value,)
        conn.commit()

        for bad in ("timed_out", "waiting", "Running"):
            with pytest.raises(psycopg.errors.InvalidTextRepresentation):
                with conn.cursor() as cur:
                    cur.execute(
                        "UPDATE data.workflow_run_executions SET status = %s "
                        "WHERE workflow_run_id = %s",
                        (bad, run_id),
                    )
            conn.rollback()
    finally:
        conn.close()


# --- 평면과 GRANT ------------------------------------------------------------------


def test_data_role_reads_and_writes_the_execution_row_including_lease(
    control_connection_factory: _Factory, data_connection_factory: _Factory
) -> None:
    """spec 0005 2.9 개정 2: worker 역할(`aether_data`)이 실행 상태·lease 를 INSERT·UPDATE 한다.
    같은 Run 의 행은 하나(PK)."""
    run_id = _seed_workflow_run(control_connection_factory)
    lease_until = datetime(2026, 1, 1, tzinfo=UTC)
    conn = data_connection_factory()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO data.workflow_run_executions (workflow_run_id) VALUES (%s)", (run_id,)
            )
            cur.execute(
                "UPDATE data.workflow_run_executions SET status = 'running', status_seq = 1, "
                "current_node_id = 's', lease_owner = 'worker-1', lease_until = %s, "
                "waiting_run_id = %s WHERE workflow_run_id = %s "
                "RETURNING status::text, lease_owner, current_node_id",
                (lease_until, uuid.uuid4(), run_id),
            )
            assert cur.fetchone() == ("running", "worker-1", "s")
        conn.commit()
        with pytest.raises(psycopg.errors.UniqueViolation):
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO data.workflow_run_executions (workflow_run_id) VALUES (%s)",
                    (run_id,),
                )
        conn.rollback()
        with pytest.raises(psycopg.errors.ForeignKeyViolation):
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO data.workflow_run_executions (workflow_run_id) VALUES (%s)",
                    (uuid.uuid4(),),
                )
        conn.rollback()
    finally:
        conn.close()


def test_control_role_has_no_access_to_workflow_run_executions(
    control_connection_factory: _Factory, admin_connection_factory: _Factory
) -> None:
    """spec 0005 2.9 개정 2, 0001 R-7: `aether_control` 에는 아무 것도 주지 않았다.

    두 겹: (1) 동작 — SELECT·INSERT·UPDATE 가 권한 부족. (2) ACL — `has_table_privilege` 가
    모든 권한에서 거짓(스키마 USAGE 부재와 무관하게 표 GRANT 한 줄을 가린다)."""
    admin = admin_connection_factory()
    try:
        for privilege in ("SELECT", "INSERT", "UPDATE", "DELETE"):
            assert not _has_privilege(admin, "aether_control", _TABLE, privilege), privilege
    finally:
        admin.close()

    conn = control_connection_factory()
    try:
        for sql in (
            f"SELECT * FROM {_TABLE}",
            f"INSERT INTO {_TABLE} (workflow_run_id) VALUES ('{uuid.uuid4()}')",
            f"UPDATE {_TABLE} SET status = 'running'",
        ):
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                with conn.cursor() as cur:
                    cur.execute(sql)
            conn.rollback()
    finally:
        conn.close()


def test_data_role_grants_are_not_widened_on_control_tables(
    admin_connection_factory: _Factory,
) -> None:
    """spec 0005 2.9 개정 2: GRANT 를 넓히지 않았다 — `aether_data` 는 `control.workflow_runs`·
    `workflow_versions` 에 여전히 SELECT 뿐이고 실행 표에는 전부 가진다."""
    conn = admin_connection_factory()
    try:
        for table in ("control.workflow_runs", "control.workflow_versions"):
            assert _has_privilege(conn, "aether_data", table, "SELECT"), table
            for privilege in ("INSERT", "UPDATE", "DELETE"):
                assert not _has_privilege(conn, "aether_data", table, privilege), (
                    table,
                    privilege,
                )
        for privilege in ("SELECT", "INSERT", "UPDATE", "DELETE"):
            assert _has_privilege(conn, "aether_data", _TABLE, privilege), privilege
    finally:
        conn.close()


# --- 투영: PostgresWorkflowRunDeclarationStore --------------------------------------


def _store(connect: _Factory) -> PostgresWorkflowRunDeclarationStore:
    return PostgresWorkflowRunDeclarationStore(connect)


def _apply(
    store: PostgresWorkflowRunDeclarationStore, run_id: uuid.UUID, seq: int, **overrides: Any
) -> bool:
    fields: dict[str, Any] = {
        "status": WorkflowRunStatus.RUNNING,
        "current_node_id": None,
        "waiting_run_id": None,
        "started_at": None,
        "finished_at": None,
        "failure_reason": None,
    }
    fields.update(overrides)
    return store.apply_status(run_id, seq=seq, **fields)


def test_create_declares_a_queued_run_with_status_seq_zero_and_joins_version(
    control_connection_factory: _Factory, admin_connection_factory: _Factory
) -> None:
    """spec 0005 2.3: 선언은 `queued`, `status_seq = 0` 이고 `get` 이 같은 뷰를 돌려준다.
    `workflow_id`·`workflow_version` 은 `workflow_versions` 와 join 으로 채워진다. `input` 은
    jsonb."""
    connect = control_connection_factory
    view = PostgresWorkflowRepository(connect).create(
        f"wf-{uuid.uuid4()}",
        (Node("s", NodeKind.START), Node("e", NodeKind.END)),
        (Edge("s", "e"),),
    )
    store = _store(connect)

    created = store.create(view.id, 1, {"k": [1, 2]}, _issue_key(connect))
    fetched = store.get(created.workflow_run_id)

    assert fetched == created
    assert created.workflow_id == view.id
    assert created.workflow_version == 1
    assert created.status == WorkflowRunStatus.QUEUED
    assert created.current_node_id is None
    assert created.started_at is None
    admin = admin_connection_factory()
    try:
        with admin.cursor() as cur:
            cur.execute(
                "SELECT status_seq, input, workflow_version_id FROM control.workflow_runs "
                "WHERE id = %s",
                (created.workflow_run_id,),
            )
            assert cur.fetchone() == (0, {"k": [1, 2]}, created.workflow_version_id)
    finally:
        admin.close()


def test_create_with_null_input_and_unknown_version(
    control_connection_factory: _Factory, admin_connection_factory: _Factory
) -> None:
    """`input` 이 없으면 SQL NULL(JSON null 이 아니다). 없는 Version 은 `WorkflowVersionNotFound`
    이고 행이 늘지 않는다."""
    connect = control_connection_factory
    view = PostgresWorkflowRepository(connect).create(
        f"wf-{uuid.uuid4()}",
        (Node("s", NodeKind.START), Node("e", NodeKind.END)),
        (Edge("s", "e"),),
    )
    store = _store(connect)

    key = _issue_key(connect)
    created = store.create(view.id, 1, None, key)
    with pytest.raises(WorkflowVersionNotFound):
        store.create(view.id, 2, None, key)

    admin = admin_connection_factory()
    try:
        with admin.cursor() as cur:
            cur.execute(
                "SELECT input IS NULL FROM control.workflow_runs WHERE id = %s",
                (created.workflow_run_id,),
            )
            assert cur.fetchone() == (True,)
            cur.execute(
                "SELECT count(*) FROM control.workflow_runs r "
                "JOIN control.workflow_versions v ON v.id = r.workflow_version_id "
                "WHERE v.workflow_id = %s",
                (view.id,),
            )
            assert cur.fetchone() == (1,)
    finally:
        admin.close()


def test_get_unknown_run_returns_none(control_connection_factory: _Factory) -> None:
    assert _store(control_connection_factory).get(uuid.uuid4()) is None


def test_apply_status_is_monotonic_in_seq(control_connection_factory: _Factory) -> None:
    """spec 0005 2.9 개정 2: `seq` 2 → 1 순서로 불러도 결과는 `seq` 2 의 것이다. 낮거나 같은
    `seq` 는 적용되지 않고(`False`), 더 높은 `seq` 는 적용된다."""
    run_id = _seed_workflow_run(control_connection_factory)
    store = _store(control_connection_factory)

    assert _apply(store, run_id, 2, status=WorkflowRunStatus.RUNNING, current_node_id="s") is True
    assert _apply(store, run_id, 1, status=WorkflowRunStatus.FAILED, current_node_id="x") is False
    assert _apply(store, run_id, 2, status=WorkflowRunStatus.FAILED) is False

    view = store.get(run_id)
    assert view is not None
    assert view.status == WorkflowRunStatus.RUNNING
    assert view.current_node_id == "s"

    assert _apply(store, run_id, 3, status=WorkflowRunStatus.SUCCEEDED) is True
    after = store.get(run_id)
    assert after is not None
    assert after.status == WorkflowRunStatus.SUCCEEDED


def test_apply_status_none_fields_do_not_erase_previous_values(
    control_connection_factory: _Factory,
) -> None:
    """spec 0005 2.9 개정 2: `started_at` 을 주지 않은 호출이 이전 값을 지우지 않는다
    (`COALESCE(new, old)`). 현재 노드·기다리는 Run·종료 시각·사유도 같다."""
    run_id = _seed_workflow_run(control_connection_factory)
    store = _store(control_connection_factory)
    started = datetime(2026, 1, 1, 1, tzinfo=UTC)
    finished = datetime(2026, 1, 1, 2, tzinfo=UTC)
    child = _seed_agent_run_id(control_connection_factory)

    assert _apply(
        store,
        run_id,
        1,
        status=WorkflowRunStatus.WAITING_RUN,
        current_node_id="a",
        waiting_run_id=child,
        started_at=started,
    )
    assert _apply(
        store,
        run_id,
        2,
        status=WorkflowRunStatus.FAILED,
        finished_at=finished,
        failure_reason="unsupported_node_kind",
    )

    view = store.get(run_id)
    assert view is not None
    assert view.status == WorkflowRunStatus.FAILED
    assert view.started_at == started
    assert view.current_node_id == "a"
    assert view.finished_at == finished
    assert view.failure_reason == "unsupported_node_kind"


def test_waiting_run_id_is_cleared_when_the_status_leaves_waiting_run(
    control_connection_factory: _Factory,
) -> None:
    """`waiting_run_id` 는 **상태에서 유도**됩니다 — `waiting_run` 일 때만 값이 있습니다.

    `COALESCE` 로 두면 스트림이 값을 지우는 신호를 실을 수 없어 기다림이 끝난 Run 에
    기다리던 대상이 남습니다(`succeeded` 인데 자식 Run 을 기다리는 것처럼 보임). 파킹을
    만드는 PR B 가 이 불변식에 의존하므로 여기서 판정합니다(spec 2.3 D-2, R-13).
    """
    run_id = _seed_workflow_run(control_connection_factory)
    store = _store(control_connection_factory)
    child = _seed_agent_run_id(control_connection_factory)

    assert _apply(store, run_id, 1, status=WorkflowRunStatus.WAITING_RUN, waiting_run_id=child)
    parked = store.get(run_id)
    assert parked is not None
    assert parked.waiting_run_id == child, "대기 중에는 기다리는 대상이 보여야 합니다(R-13)"

    assert _apply(store, run_id, 2, status=WorkflowRunStatus.RUNNING)
    resumed = store.get(run_id)
    assert resumed is not None
    assert resumed.waiting_run_id is None

    assert _apply(store, run_id, 3, status=WorkflowRunStatus.SUCCEEDED, waiting_run_id=child)
    done = store.get(run_id)
    assert done is not None
    assert done.waiting_run_id is None, "종결 상태는 무엇도 기다리지 않습니다"


def test_apply_status_for_unknown_run_returns_false(control_connection_factory: _Factory) -> None:
    assert _apply(_store(control_connection_factory), uuid.uuid4(), 1) is False


def _seed_agent_run_id(connect: _Factory) -> uuid.UUID:
    """`control.runs` 의 id 하나 — `waiting_run_id` FK 를 만족시키는 자식 Run 선언."""
    from aether_api.adapters.outbound.db.agent_repository import PostgresAgentRepository
    from aether_api.adapters.outbound.db.api_keys import PostgresApiKeyStore
    from aether_api.adapters.outbound.db.run_declaration_store import PostgresRunDeclarationStore
    from aether_api.application.usecases.issue_api_key import IssueApiKeyUseCase
    from aether_runtime.domain.agent import AgentDefinition

    definition = AgentDefinition.model_validate({"schema_version": 1, "system_prompt": "x"})
    agent = PostgresAgentRepository(connect).create(f"child-{uuid.uuid4()}", definition)
    version = PostgresAgentRepository(connect).get_version(agent.id, 1)
    requested_by = IssueApiKeyUseCase(PostgresApiKeyStore(connect))(f"k-{uuid.uuid4()}").key.id
    return (
        PostgresRunDeclarationStore(connect)
        .create(agent.id, version.id, 1, "x", requested_by)
        .run_id
    )
