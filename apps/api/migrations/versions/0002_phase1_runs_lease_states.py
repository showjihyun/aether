"""Run 투영·선언 열, lease 열, `data.run_states` 신설 (spec 0002 2.10, D-12, R-6, R-11)

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-12

Phase 1 이 `Run` 의 상태 기계·lease·재개(`RunStateStore`)를 갖기 위해 필요한 열과 테이블을
더합니다. 이 마이그레이션은 스키마·역할 경계(spec 0001 R-7)를 넓히지 않습니다 —
`aether_control` 은 여전히 `data` 스키마에 아무 권한이 없고, 새로 생기는 `data.run_states`
는 `aether_data` 에만 권한을 줍니다.

`control.runs.input` 은 지금 테이블에 행이 없다는 전제(Phase 0 은 API 가 아직 Run 을
쓰지 않음)로 `NOT NULL` 을 목표로 하지만, 서버 기본값을 잠깐 걸었다가(`''`) 곧바로
제거하는 안전한 경로를 씁니다 — 그러면 이 마이그레이션이 실행되는 시점에 행이 있어도
없어도 둘 다 통과하고, 이후의 INSERT 는 `input` 을 명시해야 합니다(기본값이 없으므로).
`status` 는 반대로 기본값(`'queued'`)을 **유지**합니다 — 투영 열이라 선언 시점에는
아직 실행 상태를 모르기 때문입니다(spec 2.10).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_DATA_ROLE = "aether_data"


def upgrade() -> None:
    # control.agents.current_version -- PUT 의 직렬화 잠금 대상이자 조회의 정본.
    op.add_column(
        "agents",
        sa.Column(
            "current_version",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("1"),
        ),
        schema="control",
    )

    # control.runs -- 투영·선언 열. `input` 은 기본값을 잠깐 걸었다가 뗍니다(주석 참조).
    op.add_column(
        "runs",
        sa.Column("input", sa.Text(), nullable=False, server_default=sa.text("''")),
        schema="control",
    )
    op.execute("ALTER TABLE control.runs ALTER COLUMN input DROP DEFAULT")
    op.add_column(
        "runs",
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'queued'")),
        schema="control",
    )
    op.add_column("runs", sa.Column("status_seq", sa.Integer(), nullable=True), schema="control")
    op.add_column(
        "runs",
        sa.Column("started_at", sa.TIMESTAMP(timezone=True), nullable=True),
        schema="control",
    )
    op.add_column(
        "runs",
        sa.Column("finished_at", sa.TIMESTAMP(timezone=True), nullable=True),
        schema="control",
    )
    op.add_column("runs", sa.Column("failure_reason", sa.Text(), nullable=True), schema="control")
    op.add_column("runs", sa.Column("trace_id", sa.Text(), nullable=True), schema="control")
    op.add_column(
        "runs",
        sa.Column("cancel_requested_at", sa.TIMESTAMP(timezone=True), nullable=True),
        schema="control",
    )

    # data.run_executions -- lease 열(spec 0002 D-10).
    op.add_column(
        "run_executions", sa.Column("lease_owner", sa.Text(), nullable=True), schema="data"
    )
    op.add_column(
        "run_executions",
        sa.Column("lease_until", sa.TIMESTAMP(timezone=True), nullable=True),
        schema="data",
    )

    # data.run_states -- 신설. `RunStateStore`(P1-2b)가 재개 가능한 `State` 를 영속합니다.
    op.create_table(
        "run_states",
        sa.Column(
            "run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("control.runs.id"),
            primary_key=True,
        ),
        sa.Column("state", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        schema="data",
    )

    # GRANT: aether_data 는 data.run_states 전부. aether_control 의 data 권한은 그대로 없음(R-7).
    op.execute(f"GRANT ALL PRIVILEGES ON data.run_states TO {_DATA_ROLE}")


def downgrade() -> None:
    op.execute(f"REVOKE ALL PRIVILEGES ON data.run_states FROM {_DATA_ROLE}")
    op.drop_table("run_states", schema="data")

    op.drop_column("run_executions", "lease_until", schema="data")
    op.drop_column("run_executions", "lease_owner", schema="data")

    op.drop_column("runs", "cancel_requested_at", schema="control")
    op.drop_column("runs", "trace_id", schema="control")
    op.drop_column("runs", "failure_reason", schema="control")
    op.drop_column("runs", "finished_at", schema="control")
    op.drop_column("runs", "started_at", schema="control")
    op.drop_column("runs", "status_seq", schema="control")
    op.drop_column("runs", "status", schema="control")
    op.drop_column("runs", "input", schema="control")

    op.drop_column("agents", "current_version", schema="control")
