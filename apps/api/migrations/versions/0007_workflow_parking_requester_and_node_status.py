"""Workflow 요청자 열, 노드 실행 상태 enum, 파킹이 풀어야 하는 FK 둘 (spec 0005 2.5 개정 3, P4-2a
B2)

Revision ID: 0007
Revises: 0006
Create Date: 2026-10-14

**1. `control.workflow_runs.requested_by uuid NULL REFERENCES control.api_keys(id)`.** 자식 Agent
Run 의 `requested_by` 를 비우면 기존 `GET /runs/{id}` 가 500 입니다(`RunView` 가 값을 필수로
요구합니다). 사람 주체를 발명하지 않고 **Workflow 를 시작한 주체**를 자식에게 그대로 물려줍니다 -
책임의 사슬이 끊기지 않고 Run API 의 계약도 바뀌지 않습니다. spec 개정 3 의 "비웁니다" 를
고칩니다. 열은 NULL 허용입니다: 0007 이전에 만들어진 행은 요청자를 모르고, 실행기는 그런 Run 의
`AGENT` 노드를 실패시킵니다(`workflow_run_without_requester`). `aether_data` 는 이 표에 이미
SELECT 가 있으므로(0005) **GRANT 변경이 없습니다.**

**2. `data.workflow_node_executions.status` 를 enum 으로 좁힙니다.** `data.workflow_node_execution_
status`(`running`·`waiting_run`·`succeeded`·`failed`)는 `data.run_execution_status`(0001)와
**다른 타입**입니다 - Agent Run 의 `waiting`·`queued`·`timed_out`·`cancelled` 가 노드 실행에는
없고, 노드 실행의 `waiting_run` 은 Workflow Run 의 같은 이름 상태와 같은 뜻입니다(자식 Run 을
기다림). 0005 가 `text` 로 열어 두고 "실행기가 집합을 정한 뒤 좁힌다" 고 남긴 자리입니다.

**3. FK 둘을 풉니다 - 이 마이그레이션의 범위를 넓히는 결정이고 리뷰 대상입니다.**
`data.workflow_node_executions.agent_run_id` 와 `control.workflow_runs.waiting_run_id` 는 0005 에서
`control.runs(id)` 를 참조했습니다. 그런데 파킹의 순서는 (a) 자식 Run 의 id 를 **정해서 영속**하고
(b) api 에 선언을 요청(`aether:workflow:agent_runs:requested`)하고 (c) 파킹 통지를 내는 것이며,
(a) 를 (b) 뒤로 미룰 수 없습니다 - 순서가 반대면 재전달에서 id 를 다시 만들어 자식 Run 이 둘이
됩니다(R-8). 그러면 (a) 시점에 `control.runs` 행이 아직 없어 FK 가 거부합니다. `waiting_run_id`
도 같은 경쟁입니다: 파킹 통지(`aether:workflow_runs:status`)와 자식 선언(`aether:workflow:agent_
runs:requested`)을 서로 다른 api 소비자가 따로 받으므로 투영이 선언보다 먼저 적용될 수 있고,
그때 FK 위반은 투영 소비자 스레드를 죽입니다(소비자는 예외를 올립니다). `data.workflow_run_
executions.waiting_run_id` 가 0006 에서 FK 없이 열린 것과 같은 근거입니다 - 이 열들은 "무엇을
기다리는가" 를 가리키는 포인터이고, 참조 무결성의 보증은 FK 가 아니라 id 를 한 곳(실행기)에서
정해 멱등 선언하는 구조가 맡습니다.

`downgrade()` 는 역순입니다: FK 복원 -> `status` 를 `text` 로 -> 열 DROP. FK 를 되돌리기 전에
`control.
runs` 에 행이 없는(아직 선언되지 않았거나 선언되지 않을) 참조는 NULL 로 바꿉니다 - 그 포인터가
가리키는
자식 Run 은 존재한 적이 없으므로 잃는 정보가 없습니다. 선언된 Run 을 가리키는 참조는 그대로
남습니다.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_NODE_STATUS_TYPE = "workflow_node_execution_status"
_NODE_STATUS_VALUES = ("running", "waiting_run", "succeeded", "failed")

_NODE_AGENT_RUN_FK = "workflow_node_executions_agent_run_id_fkey"
_RUNS_WAITING_FK = "workflow_runs_waiting_run_id_fkey"


def upgrade() -> None:
    op.add_column(
        "workflow_runs",
        sa.Column(
            "requested_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("control.api_keys.id"),
            nullable=True,
        ),
        schema="control",
    )

    values = ", ".join(f"'{v}'" for v in _NODE_STATUS_VALUES)
    op.execute(f"CREATE TYPE data.{_NODE_STATUS_TYPE} AS ENUM ({values})")
    op.execute("ALTER TABLE data.workflow_node_executions ALTER COLUMN status DROP DEFAULT")
    op.execute(
        "ALTER TABLE data.workflow_node_executions "
        f"ALTER COLUMN status TYPE data.{_NODE_STATUS_TYPE} "
        f"USING status::data.{_NODE_STATUS_TYPE}"
    )
    op.execute(
        "ALTER TABLE data.workflow_node_executions "
        f"ALTER COLUMN status SET DEFAULT 'running'::data.{_NODE_STATUS_TYPE}"
    )

    op.drop_constraint(
        _NODE_AGENT_RUN_FK, "workflow_node_executions", schema="data", type_="foreignkey"
    )
    op.drop_constraint(_RUNS_WAITING_FK, "workflow_runs", schema="control", type_="foreignkey")


def downgrade() -> None:
    op.execute(
        "UPDATE control.workflow_runs SET waiting_run_id = NULL WHERE waiting_run_id IS NOT NULL "
        "AND NOT EXISTS (SELECT 1 FROM control.runs r WHERE r.id = workflow_runs.waiting_run_id)"
    )
    op.execute(
        "UPDATE data.workflow_node_executions SET agent_run_id = NULL "
        "WHERE agent_run_id IS NOT NULL AND NOT EXISTS "
        "(SELECT 1 FROM control.runs r WHERE r.id = workflow_node_executions.agent_run_id)"
    )
    op.create_foreign_key(
        _RUNS_WAITING_FK,
        "workflow_runs",
        "runs",
        ["waiting_run_id"],
        ["id"],
        source_schema="control",
        referent_schema="control",
    )
    op.create_foreign_key(
        _NODE_AGENT_RUN_FK,
        "workflow_node_executions",
        "runs",
        ["agent_run_id"],
        ["id"],
        source_schema="data",
        referent_schema="control",
    )

    op.execute("ALTER TABLE data.workflow_node_executions ALTER COLUMN status DROP DEFAULT")
    op.execute(
        "ALTER TABLE data.workflow_node_executions ALTER COLUMN status TYPE text USING status::text"
    )
    op.execute(
        "ALTER TABLE data.workflow_node_executions ALTER COLUMN status SET DEFAULT 'running'"
    )
    op.execute(f"DROP TYPE data.{_NODE_STATUS_TYPE}")

    op.drop_column("workflow_runs", "requested_by", schema="control")
