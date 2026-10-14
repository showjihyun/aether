"""Workflow Run 의 실행 상태와 lease 표 `data.workflow_run_executions` (spec 0005 2.9 개정 2, P4-2a)

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-14

**왜 `data` 인가.** 실행기는 worker 이고 worker 의 역할(`aether_data`)은 `control` 에
SELECT 뿐입니다(0001·0005 의 GRANT). 그래서 worker 는 `control.workflow_runs` 에 상태·lease·
현재 노드를 쓸 수 없습니다. GRANT 를 넓히지 않습니다 — spec D-5 의 평면 규칙(쓰는 주체가
평면을 가른다)을 거스르고 권한 변경은 사람 검토 대상이기 때문입니다. 대신 Phase 1·3 이 이미
쓰는 모양을 그대로 따릅니다: 실행 상태는 `data`(이 표), `control.workflow_runs` 는 **투영**이고
`aether:workflow_runs:status` 스트림으로 api 가 갱신합니다(`data.run_executions` →
`aether:runs:status` → `control.runs` 와 같은 선).

**enum 을 새로 만들지 않고 재사용한 이유.** `status` 열은 0005 가 만든
`control.workflow_run_status` 를 그대로 씁니다. 같은 값 집합을 두 타입으로 복제하면 한쪽에만
값이 늘어 어긋날 수 있고, `aether_data` 는 스키마 `control` 에 USAGE 가 있어(0001) 그 타입을
컬럼 타입으로 쓸 수 있습니다(통합 테스트가 실제로 쓸 수 있음을 확인합니다).

`waiting_run_id` 에는 FK 를 두지 않습니다 — worker 가 소유하는 열이고 의미는 파킹(PR B)과
승인(P4-4)에서 늘어납니다. `workflow_run_id` 는 `control.workflow_runs` 를 참조합니다
(`data` → `control` FK 는 0004·0005 에 선례가 있습니다).

GRANT: `aether_data` 에 전부. `aether_control` 에는 아무 것도 주지 않습니다(0001 R-7 유지).

`downgrade()` 는 REVOKE → DROP TABLE 순서입니다.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_DATA_ROLE = "aether_data"

_WORKFLOW_RUN_STATUS_VALUES = (
    "queued",
    "running",
    "waiting_run",
    "waiting_approval",
    "succeeded",
    "failed",
    "cancelled",
)


def upgrade() -> None:
    op.create_table(
        "workflow_run_executions",
        sa.Column(
            "workflow_run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("control.workflow_runs.id"),
            primary_key=True,
        ),
        sa.Column(
            "status",
            postgresql.ENUM(
                *_WORKFLOW_RUN_STATUS_VALUES,
                name="workflow_run_status",
                schema="control",
                create_type=False,
            ),
            nullable=False,
            server_default=sa.text("'queued'"),
        ),
        sa.Column("status_seq", sa.BigInteger(), nullable=False, server_default=sa.text("0")),
        sa.Column("current_node_id", sa.Text(), nullable=True),
        sa.Column("waiting_run_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("lease_owner", sa.Text(), nullable=True),
        sa.Column("lease_until", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("started_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("finished_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        schema="data",
    )
    op.execute(f"GRANT ALL PRIVILEGES ON data.workflow_run_executions TO {_DATA_ROLE}")


def downgrade() -> None:
    op.execute(f"REVOKE ALL PRIVILEGES ON data.workflow_run_executions FROM {_DATA_ROLE}")
    op.drop_table("workflow_run_executions", schema="data")
