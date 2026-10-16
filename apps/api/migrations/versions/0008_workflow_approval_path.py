"""승인 경로 - 지목 대상 투영, 노드 실행 waiting_approval, 승인 unique, 승인 SELECT GRANT

Revision ID: 0008
Revises: 0007
Create Date: 2026-10-15

(spec 0005 2.6 개정 5, P4-4)

> **사람 검토 항목 (H-1, DP-6) - 아래 5번의 `GRANT SELECT` 한 줄입니다.**
> 이 마이그레이션은 worker 역할(`aether_data`)에 `control.workflow_approvals`
> 를 **읽는 권한** 을 처음 줍니다. 나머지 변경은 이 한 줄을 위한 것이거나
> 이 한 줄과 무관한 정확성 변경입니다. **쓰기 권한은 주지 않습니다.**

승인 경로(P4-4)가 평면 규칙 때문에 막힌 곳 둘을 풉니다. 둘 다 승인자 권한
모델과 무관합니다 - 그 모델은 만들지 않습니다(spec C-4, Phase 8 의 자리).

**1. `waiting_node_execution_id uuid NULL` 열 둘** -
`control.workflow_runs` 와 `data.workflow_run_executions`.
승인 API 는 지목한 노드 실행이 **그 Run 이 지금 기다리는 것인지** 를 보고
아니면 4xx 로 거부해야 합니다(R-12). 그런데 노드 실행은 `data` 에 있고
api 역할(`aether_control`)은 `data` 에 아무 권한이 없습니다(0001 R-7).
그래서 "지금 어느 노드 실행을 기다리는가" 를 `control` 로 **투영**합니다.
`waiting_run_id` 와 같은 모양, 같은 불변식입니다: `waiting_approval` 일
때만 값이 있고 다른 상태로 가면 지워집니다(상태에서 유도).
실행 상태의 정본은 `data` 쪽 열이고 `control` 쪽은
`aether:workflow_runs:status` 로 api 가 갱신하는 투영입니다.
두 열 모두 **FK 가 없습니다** - 0007 이 풀어 준 두 포인터와 같은 근거
(평면을 넘는 포인터이고 노드 실행 행은 `data` 에 있습니다)입니다.

**2. `data.workflow_node_execution_status` 에 `waiting_approval` 추가.**
이 enum 은 0007 이 `data.run_execution_status`(Agent Run 의 것)와
**다른 타입** 으로 만들었습니다. Agent Run 의 `waiting` 값은 건드리지
않습니다(R-13 회귀). `downgrade()` 는 enum 값을 지울 수 없으므로 타입을
새로 만들어 바꿔 끼웁니다 - 그때 `waiting_approval` 인 행은 지우지 않고
`running` 으로 둡니다(시작만 하고 멈춘 노드와 같은 모양이라 데이터를
잃지 않습니다).

**3. `unique(workflow_run_id, node_execution_id)`** on
`control.workflow_approvals`. 승인은 노드 실행당 **한 건** 입니다.
승인 API 를 두 번 불러도 기록이 두 건 되지 않게 DB 가 지킵니다(R-8 의
승인 판). append-only 트리거(0005)와 함께 "기록이 1건" 을 앱의 예의가
아니라 제약으로 보장합니다.

**4. 이 마이그레이션이 하지 않는 것.** 승인자를 판정하는 열·표·제약을
더하지 않습니다. `approved_by` 는 0005 가 만든 `text` 그대로 **인증된
주체의 id 를 적을 뿐** 입니다.

**5. `GRANT SELECT ON control.workflow_approvals TO aether_data`** -
검토 대상. 0005 가 "승인 경로(P4-4)가 필요로 하면 그때 검토를 거쳐
더한다" 고 비워 둔 자리입니다.

*왜 필요한가.* 승인을 받은 뒤 Workflow Run 을 재개하는 것은 worker 의
실행기입니다. 실행기는 "이 노드 실행에 승인이 있는가" 를 알아야 전진합니다.

*왜 메시지로는 안 되는가.* api 가 승인을 기록하고
`aether:workflow_runs:requested` 에 재큐 메시지를 넣는 것만으로 실행기가
전진하게 만들 수도 있습니다. 하지만 그러면 **전진의 근거가 메시지** 가
됩니다. 재큐 메시지는 스위퍼도, 중복 전달도, 오래된 PEL 의 재시도도,
스트림에 쓸 수 있는 누구라도 만들 수 있고, 떠돌이 메시지 하나가 승인
없이 Workflow 를 전진시킵니다(R-12 가 무너집니다). 전진의 근거는
**저장된 사실** 이어야 하고, 그래서 실행기가 승인 표를 직접 읽습니다.
메시지는 "다시 보라" 는 신호일 뿐이고 판정은 읽은 사실로 합니다.
같은 이유로 스위퍼도 승인이 이미 있는 건만 줍습니다(재큐 유실의
안전망, spec 2.5).

*왜 SELECT 만인가.* 실행기가 승인을 쓸 이유가 없습니다. 쓰기는 api 의
일이고, worker 가 쓸 수 있으면 "읽기 경로" 가 승인을 만들어 내는 길이
됩니다. INSERT·UPDATE·DELETE 는 주지 않으며(통합 테스트가 권한 부족으로
거부됨을 확인합니다) 이 표는 트리거로도 UPDATE·DELETE 가 막힌
append-only 입니다.

*읽히는 것.* `approved_by`(인증된 주체의 id)와 `note` 도 이 표의 열이라
테이블 단위 SELECT 는 그것까지 읽을 수 있게 합니다. 실행기 어댑터
(`PostgresApprovalReader`)는 `node_execution_id`·`approved_at` 만 SELECT
합니다. 열 단위 GRANT(`node_execution_id`, `approved_at`)로 더 좁히는
것도 가능하며 검토자가 고를 선택지입니다 - 이 마이그레이션은 지시된 대로
테이블 단위입니다.

`aether_control` 에는 바뀌는 권한이 없습니다(이미 전부). `aether_control`
은 `data` 에 여전히 아무 권한이 없습니다(0001 R-7).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_DATA_ROLE = "aether_data"
_NODE_STATUS_TYPE = "workflow_node_execution_status"
_NODE_STATUS_OLD_VALUES = ("running", "waiting_run", "succeeded", "failed")
_UNIQUE_NAME = "uq_workflow_approvals_run_node_execution"


def upgrade() -> None:
    op.add_column(
        "workflow_runs",
        sa.Column("waiting_node_execution_id", postgresql.UUID(as_uuid=True), nullable=True),
        schema="control",
    )
    op.add_column(
        "workflow_run_executions",
        sa.Column("waiting_node_execution_id", postgresql.UUID(as_uuid=True), nullable=True),
        schema="data",
    )

    op.execute(
        f"ALTER TYPE data.{_NODE_STATUS_TYPE} ADD VALUE 'waiting_approval' AFTER 'waiting_run'"
    )

    op.create_unique_constraint(
        _UNIQUE_NAME,
        "workflow_approvals",
        ["workflow_run_id", "node_execution_id"],
        schema="control",
    )

    # H-1: 이 한 줄이 사람 검토 항목입니다. SELECT 보다 넓게 주지 않습니다.
    op.execute(f"GRANT SELECT ON control.workflow_approvals TO {_DATA_ROLE}")


def downgrade() -> None:
    op.execute(f"REVOKE SELECT ON control.workflow_approvals FROM {_DATA_ROLE}")

    op.drop_constraint(_UNIQUE_NAME, "workflow_approvals", schema="control", type_="unique")

    # enum 값은 지울 수 없다 -> 타입을 새로 만들어 바꿔 끼운다. `waiting_approval` 인 행은 지우지
    # 않고 `running` 으로 둔다(시작만 하고 멈춘 노드와 같은 모양).
    old_values = ", ".join(f"'{v}'" for v in _NODE_STATUS_OLD_VALUES)
    op.execute(
        "UPDATE data.workflow_node_executions SET status = 'running' "
        "WHERE status = 'waiting_approval'"
    )
    op.execute("ALTER TABLE data.workflow_node_executions ALTER COLUMN status DROP DEFAULT")
    op.execute(f"CREATE TYPE data.{_NODE_STATUS_TYPE}_old AS ENUM ({old_values})")
    op.execute(
        "ALTER TABLE data.workflow_node_executions "
        f"ALTER COLUMN status TYPE data.{_NODE_STATUS_TYPE}_old "
        f"USING status::text::data.{_NODE_STATUS_TYPE}_old"
    )
    op.execute(f"DROP TYPE data.{_NODE_STATUS_TYPE}")
    op.execute(f"ALTER TYPE data.{_NODE_STATUS_TYPE}_old RENAME TO {_NODE_STATUS_TYPE}")
    op.execute(
        "ALTER TABLE data.workflow_node_executions "
        f"ALTER COLUMN status SET DEFAULT 'running'::data.{_NODE_STATUS_TYPE}"
    )

    op.drop_column("workflow_run_executions", "waiting_node_execution_id", schema="data")
    op.drop_column("workflow_runs", "waiting_node_execution_id", schema="control")
