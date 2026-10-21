"""노드 실행 투영 표 `control.workflow_node_states` (spec 0007 2.3, D-3, D-4 · 개정 1, P5-1)

Revision ID: 0012
Revises: 0011
Create Date: 2026-10-21

**왜 이 표인가.** 노드 실행의 정본은 `data.workflow_node_executions` 이고 api 역할
(`aether_control`)은 `data` 에 권한이 0건입니다(0001 R-7). 그래서 화면(P5-3)이 노드 실행을 보려면
`control` 쪽에 **투영**이 있어야 합니다. 선례는 `control.workflow_runs`(0005, `data.workflow_run_
executions` 의 투영)와 같은 모양입니다 - worker 가 스트림으로 통지하고 api 가 이 표에 씁니다.

**열은 화면이 쓰는 것만.** `workflow_run_id`·`node_id`·`kind`·`status`·`status_seq`·
`started_at`·`finished_at`·`failure_reason`. **노드 출력(`output`)·입력·자식 Run id 를 넣지
않습니다**(D-4) - 넣으면 spec 0005 D-8 의 "출력은 `data` 에 머문다" 를 되돌리는 일이고
`tests/arch/test_workflow_output_stays_in_data.py` 가 발화합니다.

**이름이 `node_states` 인 이유.** spec 초안은 이 표를 `control.workflow_node_executions` 로
불렀지만, 그러면 정본(`data.workflow_node_executions`)과 **같은 이름이 두 평면에** 생깁니다 -
api 코드에서 그 이름을 보고 어느 평면인지 알 수 없게 되고, 그것을 지키던 구조 테스트
(`test_the_api_never_touches_the_node_execution_output`)가 먼저 발화했습니다. 이 표에는 실행
기록이 아니라 **상태**만 있으므로(출력·입력·자식 Run id 없음) 이름을 그 사실에 맞췄습니다.
spec 개정 1 [편집].

**키는 `(workflow_run_id, node_id)`.** 루프 안의 노드는 회차가 여럿이지만 화면이 보는 것은 노드당
가장 최근 상태 한 행입니다. `status_seq` 는 Workflow Run 하나 안에서 단조 증가하는 수열(이벤트의
`seq` 와 같은 수열)이라 같은 키의 늦은 메시지를 버리는 근거가 됩니다.

**`status` 는 `text` + CHECK.** `data.workflow_node_execution_status` enum 을 쓸 수 없습니다 -
`aether_control` 에는 `data` 스키마 USAGE 가 없습니다. `control` 에 새 enum 타입을 두면 "workflow 가
들어간 enum 은 둘뿐" 이라는 0006·0007 의 불변식(`test_workflow_run_executions_integration.py`)이
깨지므로, 같은 여섯 값을 CHECK 로 좁힙니다(값이 늘면 두 곳을 같이 고칩니다).

**GRANT: `aether_control` 에만.** `aether_data` 에는 이 표에 대한 권한이 한 줄도 없습니다 -
투영의 쓰는 주체는 api 하나이고(spec 0001 R-7, AR-13), worker 는 통지를 스트림으로 보냅니다.

`downgrade()` 는 REVOKE → DROP TABLE 순서입니다.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0012"
down_revision: str | None = "0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_CONTROL_ROLE = "aether_control"

_NODE_STATUS_VALUES = (
    "running",
    "waiting_run",
    "waiting_approval",
    "waiting_timer",
    "succeeded",
    "failed",
)


def upgrade() -> None:
    op.create_table(
        "workflow_node_states",
        sa.Column(
            "workflow_run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("control.workflow_runs.id"),
            primary_key=True,
        ),
        sa.Column("node_id", sa.Text(), primary_key=True),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("status_seq", sa.BigInteger(), nullable=False),
        sa.Column("started_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("finished_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "status IN (" + ", ".join(f"'{v}'" for v in _NODE_STATUS_VALUES) + ")",
            name="ck_workflow_node_states_status",
        ),
        schema="control",
    )
    op.execute(f"GRANT ALL PRIVILEGES ON control.workflow_node_states TO {_CONTROL_ROLE}")


def downgrade() -> None:
    op.execute(f"REVOKE ALL PRIVILEGES ON control.workflow_node_states FROM {_CONTROL_ROLE}")
    op.drop_table("workflow_node_states", schema="control")
