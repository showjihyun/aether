"""WAIT 타이머 대기 - `waiting_timer` 상태 둘과 `wake_at` 열 둘

Revision ID: 0009
Revises: 0008
Create Date: 2026-10-16

(spec 0005 2.7 개정 7 (5), P4-3 둘째 물결)

`WAIT` 노드는 실제 시간을 블록하지 않고 **파킹**합니다(D-4 가 금지한 슬롯 점유를 피합니다).
파킹에는 상태 하나와 깨어날 시각이 필요하고, 이 마이그레이션이 그 둘을 더합니다. **GRANT 변경은
없습니다** - 새 열은 이미 권한이 있는 표의 열이고(`aether_data` 는 `data` 쪽 표 전체에,
`aether_control`
은 `control.workflow_runs` 전체에 권한이 있습니다, 0005·0006) 통합 테스트가 0008 시점과 0009 시점의
권한 행렬이 같음을 확인합니다.

**1. `waiting_timer` 값 둘.** `control.workflow_run_status`(Workflow Run 의 상태, 두 표가
공유합니다:
`control.workflow_runs.status` 와 `data.workflow_run_executions.status`)와
`data.workflow_node_execution_status`(노드 실행의 상태, 0007). `data.run_execution_status`(Agent Run
의
것)는 건드리지 않습니다(R-13 회귀). `ALTER TYPE ... ADD VALUE` 는 같은 트랜잭션 안에서 그 값을 **쓸
수 없습니다** - 이 마이그레이션은 값을 추가만 하고 쓰지 않으므로(0008 이 `waiting_approval` 에서 한
것과 같은 모양) 트랜잭션 안에서 실행해도 안전합니다. 값을 쓰는 것은 앱이고, 마이그레이션 커밋
뒤입니다.

**2. `wake_at timestamptz NULL` 열 둘.** `data.workflow_run_executions.wake_at` 이
**정본**이고(worker 가
씁니다), `control.workflow_runs.wake_at` 은 `aether:workflow_runs:status` 로 api 가 갱신하는
**투영**입니다(api 역할 `aether_control` 은 `data` 에 권한이 없어서, 0001 R-7). `waiting_run_id`·
`waiting_node_execution_id` 와 같은 불변식입니다: `waiting_timer` 일 때만 값이 있고 다른 상태로 가면
지워집니다(상태에서 유도). **FK 가 없습니다** - 시각일 뿐 포인터가 아닙니다. 스위퍼는 정본 열의
`wake_at <= now()` 를 읽습니다(`WAIT` 에는 깨우는 외부 사건이 없어서 스위퍼가 안전망이 아니라 주
경로입니다).

**3. `downgrade()`.** enum 값은 지울 수 없으므로 타입을 **새로 만들어 바꿔 끼웁니다**(0008 이 노드
상태에서 한 것과 같은 모양). `waiting_timer` 인 행은 지우지 않고 `running` 으로 둡니다(시작만 하고
멈춘 것과 같은 모양이라 데이터를 잃지 않습니다). `control.workflow_run_status` 는 두 표의 열이
공유하므로 두 열을 함께 옮깁니다.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_RUN_TYPE = "control.workflow_run_status"
_RUN_OLD_VALUES = (
    "queued",
    "running",
    "waiting_run",
    "waiting_approval",
    "succeeded",
    "failed",
    "cancelled",
)
_RUN_COLUMNS = ("control.workflow_runs", "data.workflow_run_executions")

_NODE_TYPE = "data.workflow_node_execution_status"
_NODE_OLD_VALUES = ("running", "waiting_run", "waiting_approval", "succeeded", "failed")
_NODE_TABLE = "data.workflow_node_executions"


def upgrade() -> None:
    op.execute(f"ALTER TYPE {_RUN_TYPE} ADD VALUE 'waiting_timer' AFTER 'waiting_approval'")
    op.execute(f"ALTER TYPE {_NODE_TYPE} ADD VALUE 'waiting_timer' AFTER 'waiting_approval'")

    op.add_column(
        "workflow_runs",
        sa.Column("wake_at", sa.TIMESTAMP(timezone=True), nullable=True),
        schema="control",
    )
    op.add_column(
        "workflow_run_executions",
        sa.Column("wake_at", sa.TIMESTAMP(timezone=True), nullable=True),
        schema="data",
    )


def _swap_enum(
    type_name: str, old_values: tuple[str, ...], tables: tuple[str, ...], default: str
) -> None:
    """`type_name` 을 `old_values` 로 새로 만들어 `tables` 의 `status` 열을 옮기고 이름을
    되돌린다."""
    values = ", ".join(f"'{v}'" for v in old_values)
    bare = type_name.split(".", 1)[1]
    schema = type_name.split(".", 1)[0]
    for table in tables:
        op.execute(f"ALTER TABLE {table} ALTER COLUMN status DROP DEFAULT")
    op.execute(f"CREATE TYPE {type_name}_old AS ENUM ({values})")
    for table in tables:
        op.execute(
            f"ALTER TABLE {table} ALTER COLUMN status TYPE {type_name}_old "
            f"USING status::text::{type_name}_old"
        )
    op.execute(f"DROP TYPE {type_name}")
    op.execute(f"ALTER TYPE {type_name}_old RENAME TO {bare}")
    for table in tables:
        op.execute(
            f"ALTER TABLE {table} ALTER COLUMN status SET DEFAULT '{default}'::{schema}.{bare}"
        )


def downgrade() -> None:
    op.drop_column("workflow_run_executions", "wake_at", schema="data")
    op.drop_column("workflow_runs", "wake_at", schema="control")

    # `waiting_timer` 인 행은 지우지 않고 `running` 으로 둔다.
    for table in _RUN_COLUMNS:
        op.execute(f"UPDATE {table} SET status = 'running' WHERE status = 'waiting_timer'")
    op.execute(f"UPDATE {_NODE_TABLE} SET status = 'running' WHERE status = 'waiting_timer'")

    _swap_enum(_RUN_TYPE, _RUN_OLD_VALUES, _RUN_COLUMNS, "queued")
    _swap_enum(_NODE_TYPE, _NODE_OLD_VALUES, (_NODE_TABLE,), "running")
