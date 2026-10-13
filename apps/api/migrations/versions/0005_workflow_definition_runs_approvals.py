"""Workflow 정의·Run·승인·노드 실행 다섯 표 신설, GRANT (spec 0005 2.9, D-3, D-5, D-12, P4-1)

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-13

spec 2.9 의 다섯 표를 **한 번에** 만듭니다 — `control.workflows`·`control.workflow_versions`
(불변)·`control.workflow_runs`(Run 투영)·`control.workflow_approvals`(승인 기록,
append-only)·`data.workflow_node_executions`(노드 실행 기록과 출력). 쓰는 단위는
`workflow_runs`·`workflow_approvals`·`workflow_node_executions` 가 P4-2a·P4-4 이지만, 평면·역할·
GRANT 검토를 한 번에 끝내려고 표는 여기서 만듭니다(마이그레이션 0003 이 P2-4 의
`control.tool_permissions` 를 함께 만든 것과 같습니다).

Workflow Run 상태는 **새 enum** `control.workflow_run_status` 입니다(spec 2.3) —
`data.run_execution_status`(0001)는 건드리지 않습니다. 값에 `timed_out` 은 없습니다.
enum 이 `control` 스키마에 있는 이유: `aether_control` 은 `data` 스키마에 USAGE 가 없어
(0001 R-7) `data` 의 enum 을 컬럼 타입으로 쓰는 표를 읽을 수 없습니다.

자식 Agent Run 과의 연결은 `data.workflow_node_executions.agent_run_id` 입니다(D-3 — workflow
쪽에 둡니다. `control.runs` 에는 Workflow 참조를 넣지 않습니다, AR-13). 승인 기록이
가리키는 `node_execution_id` 에는 FK 를 두지 않습니다 — `control` 에서 `data` 를 참조하는
방향은 평면 경계를 거스르고(`data` → `control` FK 는 0004 에 선례가 있습니다), 지목한 노드
실행이 `waiting_approval` 인지는 P4-4 의 유스케이스가 판정합니다(R-12).

불변성은 DB 트리거로 보장합니다(0001 의 `agent_versions_immutable` 과 같은 방식):
`workflow_versions` 는 UPDATE·DELETE 불가(D-12), `workflow_approvals` 는 append-only.

GRANT 방향(spec 2.9, 0004 의 선례):
- `aether_control`: `control` 의 새 표 넷에 전부.
- `aether_data`: `control.workflow_versions`·`control.workflow_runs` 에 **SELECT 만**
  (worker 가 실행할 그래프와 Run 선언을 읽어야 합니다 —
  `agent_versions`·`runs` 에 이미 열려 있는 것과 같은 경계).
  `control.workflows`(이름뿐)와 `control.workflow_approvals` 에는 주지 않습니다 —
  실행기는 둘 다 읽을 이유가 없고, 승인 경로(P4-4)가 필요로 하면
  그때 검토를 거쳐 더합니다. `data.workflow_node_executions` 는 전부.
- `aether_control` 은 `data` 에 여전히 아무 권한이 없습니다(스키마 단계에서 거부, 0001 R-7).

`downgrade()` 는 GRANT/REVOKE → 트리거·함수 → 표 DROP(참조 역순) → enum 타입 DROP 순서입니다.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_CONTROL_ROLE = "aether_control"
_DATA_ROLE = "aether_data"

_WORKFLOW_RUN_STATUS_TYPE = "workflow_run_status"
_WORKFLOW_RUN_STATUS_VALUES = (
    "queued",
    "running",
    "waiting_run",
    "waiting_approval",
    "succeeded",
    "failed",
    "cancelled",
)


def _uuid_pk() -> sa.Column:  # type: ignore[type-arg]
    return sa.Column(
        "id",
        postgresql.UUID(as_uuid=True),
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    )


def _created_at(name: str = "created_at") -> sa.Column:  # type: ignore[type-arg]
    return sa.Column(
        name,
        sa.TIMESTAMP(timezone=True),
        nullable=False,
        server_default=sa.text("now()"),
    )


def upgrade() -> None:
    status_values = ", ".join(f"'{value}'" for value in _WORKFLOW_RUN_STATUS_VALUES)
    op.execute(f"CREATE TYPE control.{_WORKFLOW_RUN_STATUS_TYPE} AS ENUM ({status_values})")

    # control.workflows -- 이름과 현재 Version 번호.
    op.create_table(
        "workflows",
        _uuid_pk(),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("current_version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        _created_at(),
        _created_at("updated_at"),
        schema="control",
    )

    # control.workflow_versions -- 노드·간선. 불변(트리거 아래).
    op.create_table(
        "workflow_versions",
        _uuid_pk(),
        sa.Column(
            "workflow_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("control.workflows.id"),
            nullable=False,
        ),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("nodes", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("edges", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        _created_at(),
        sa.UniqueConstraint("workflow_id", "version", name="uq_workflow_versions_workflow_version"),
        schema="control",
    )

    # control.workflow_runs -- Run 투영(상태·현재 노드·기다리는 대상).
    op.create_table(
        "workflow_runs",
        _uuid_pk(),
        sa.Column(
            "workflow_version_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("control.workflow_versions.id"),
            nullable=False,
        ),
        sa.Column("input", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "status",
            postgresql.ENUM(
                *_WORKFLOW_RUN_STATUS_VALUES,
                name=_WORKFLOW_RUN_STATUS_TYPE,
                schema="control",
                create_type=False,
            ),
            nullable=False,
            server_default=sa.text("'queued'"),
        ),
        sa.Column("status_seq", sa.BigInteger(), nullable=False, server_default=sa.text("0")),
        sa.Column("current_node_id", sa.Text(), nullable=True),
        sa.Column(
            "waiting_run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("control.runs.id"),
            nullable=True,
        ),
        _created_at("requested_at"),
        sa.Column("started_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("finished_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column("cancel_requested_at", sa.TIMESTAMP(timezone=True), nullable=True),
        schema="control",
    )

    # control.workflow_approvals -- 승인 기록, append-only(트리거 아래). 권한 판정 없음(DP-6).
    op.create_table(
        "workflow_approvals",
        _uuid_pk(),
        sa.Column(
            "workflow_run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("control.workflow_runs.id"),
            nullable=False,
        ),
        sa.Column("node_execution_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("approved_by", sa.Text(), nullable=False),
        _created_at("approved_at"),
        sa.Column("note", sa.Text(), nullable=True),
        schema="control",
    )

    # data.workflow_node_executions -- 노드 실행 기록과 출력(8 KiB 상한은 애플리케이션이 지킵니다).
    op.create_table(
        "workflow_node_executions",
        _uuid_pk(),
        sa.Column(
            "workflow_run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("control.workflow_runs.id"),
            nullable=False,
        ),
        sa.Column("node_id", sa.Text(), nullable=False),
        sa.Column("iteration", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'running'")),
        sa.Column(
            "agent_run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("control.runs.id"),
            nullable=True,
        ),
        sa.Column("output", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "output_truncated", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        _created_at("started_at"),
        sa.Column("finished_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.UniqueConstraint(
            "workflow_run_id",
            "node_id",
            "iteration",
            name="uq_workflow_node_executions_run_node_iteration",
        ),
        schema="data",
    )

    # 불변 트리거: Version 은 앱의 예의가 아니라 DB 제약으로 불변(D-12), 승인은 append-only.
    for table in ("workflow_versions", "workflow_approvals"):
        op.execute(
            f"""
            CREATE FUNCTION control.reject_{table}_mutation() RETURNS trigger
            LANGUAGE plpgsql AS $$
            BEGIN
                RAISE EXCEPTION
                    'control.{table} is immutable: % on row % is not allowed',
                    TG_OP, OLD.id;
            END;
            $$
            """
        )
        op.execute(
            f"""
            CREATE TRIGGER {table}_immutable
            BEFORE UPDATE OR DELETE ON control.{table}
            FOR EACH ROW EXECUTE FUNCTION control.reject_{table}_mutation()
            """
        )

    # GRANT: control 의 새 표 넷은 aether_control 전부.
    for table in ("workflows", "workflow_versions", "workflow_runs", "workflow_approvals"):
        op.execute(f"GRANT ALL PRIVILEGES ON control.{table} TO {_CONTROL_ROLE}")
    # aether_data 는 실행에 필요한 둘만 SELECT.
    op.execute(f"GRANT SELECT ON control.workflow_versions TO {_DATA_ROLE}")
    op.execute(f"GRANT SELECT ON control.workflow_runs TO {_DATA_ROLE}")
    # data 의 새 표는 aether_data 전부. aether_control 은 data 에 아무 권한이 없습니다.
    op.execute(f"GRANT ALL PRIVILEGES ON data.workflow_node_executions TO {_DATA_ROLE}")


def downgrade() -> None:
    op.execute(f"REVOKE ALL PRIVILEGES ON data.workflow_node_executions FROM {_DATA_ROLE}")
    op.execute(f"REVOKE SELECT ON control.workflow_runs FROM {_DATA_ROLE}")
    op.execute(f"REVOKE SELECT ON control.workflow_versions FROM {_DATA_ROLE}")
    for table in ("workflow_approvals", "workflow_runs", "workflow_versions", "workflows"):
        op.execute(f"REVOKE ALL PRIVILEGES ON control.{table} FROM {_CONTROL_ROLE}")

    for table in ("workflow_approvals", "workflow_versions"):
        op.execute(f"DROP TRIGGER IF EXISTS {table}_immutable ON control.{table}")
        op.execute(f"DROP FUNCTION IF EXISTS control.reject_{table}_mutation()")

    op.drop_table("workflow_node_executions", schema="data")
    op.drop_table("workflow_approvals", schema="control")
    op.drop_table("workflow_runs", schema="control")
    op.drop_table("workflow_versions", schema="control")
    op.drop_table("workflows", schema="control")

    op.execute(f"DROP TYPE control.{_WORKFLOW_RUN_STATUS_TYPE}")
