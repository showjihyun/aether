"""`data.tool_call_audit` - `run_id` 의 FK 를 풀고 `run_kind` 를 더한다

Revision ID: 0010
Revises: 0009
Create Date: 2026-10-17

(spec 0005 2.8 개정 10, R-14, P4-5 - 사람 결정)

**왜.** Workflow 의 도구 호출이 감사에 남지 않았다. `tool_call_audit.run_id` 는 0003 이
`control.runs(id)` 를 가리키는 FK 로 만들었고, Workflow Run 의 id 는 `control.workflow_runs` 에
있어서 그 FK 를 만족할 수 없다. 한 열이 **두 평면의 Run**(Agent Run 과 Workflow Run)을 가리키므로
FK 로는 표현할 수 없다. 이것이 조용한 구멍이 되는 이유는 `CallToolUseCase` 가 감사 쓰기 실패를
**삼키기** 때문이다(spec 0003 D-10) - FK 가 남아 있으면 호출은 성공하는데 감사 행만 사라진다.
0007 이 같은 이유로 cross-plane FK 둘을 푼 선례가 있다: 이 열은 "어느 실행의 것인가" 를 가리키는
포인터이고 참조 무결성은 DB 가 아니라 애플리케이션이 책임진다.

**무엇을.**

1. `ALTER TABLE data.tool_call_audit DROP CONSTRAINT tool_call_audit_run_id_fkey` (0003 의
   `sa.ForeignKey` 가 PostgreSQL 기본 이름으로 만든 제약). `run_id` 는 `NOT NULL` 그대로다 -
   포인터는 항상 있다. `agent_version_id` 의 FK(`control.agent_versions`)는 건드리지 않는다:
   Workflow 노드도 실제 Agent Version 을 권한 주체로 지목한다(개정 9).
2. `run_kind text NOT NULL DEFAULT 'agent'` + `CHECK (run_kind IN ('agent', 'workflow'))`.
   기존 행은 전부 Agent Run 의 것이므로 기본값이 맞다. 감사를 읽는 쪽이 `run_id` 의 출처를
   구별하는 유일한 열이다.

**GRANT 변경은 없다.** 새 열은 이미 권한이 있는 표의 열이다(`aether_data` INSERT·SELECT 만,
append-only 그대로, 0003). 통합 테스트가 확인한다. Policy(`control.tool_permissions`)와 기본 deny
는 이 마이그레이션이 건드리지 않는다.

**downgrade() 는 감사 행을 지운다.** FK 를 되돌리려면 `run_id` 가 모두 `control.runs` 에 있어야
하는데 `run_kind = 'workflow'` 인 행의 id 는 거기에 없다. 그래서 `run_kind` 를 DROP 하기 **전에**
`workflow` 행을 **삭제**한다 - 되돌리기는 Workflow 도구 호출의 감사 기록을 **잃는다**(append-only
표에 대한 유일한 DELETE 이고, 마이그레이션 역할만 할 수 있다). `agent` 행은 남는다. 운영 DB 에서
되돌리기 전에 이 사실을 알고 있어야 한다.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLE = "data.tool_call_audit"
_FK = "tool_call_audit_run_id_fkey"
_CHECK = "ck_tool_call_audit_run_kind"


def upgrade() -> None:
    op.execute(f"ALTER TABLE {_TABLE} DROP CONSTRAINT {_FK}")
    op.execute(f"ALTER TABLE {_TABLE} ADD COLUMN run_kind text NOT NULL DEFAULT 'agent'")
    op.execute(
        f"ALTER TABLE {_TABLE} ADD CONSTRAINT {_CHECK} CHECK (run_kind IN ('agent', 'workflow'))"
    )


def downgrade() -> None:
    # 감사 행을 지운다: FK 를 복원하려면 Workflow Run id 를 가진 행이 남을 수 없다.
    op.execute(f"DELETE FROM {_TABLE} WHERE run_kind = 'workflow'")
    op.execute(f"ALTER TABLE {_TABLE} DROP CONSTRAINT {_CHECK}")
    op.execute(f"ALTER TABLE {_TABLE} DROP COLUMN run_kind")
    op.execute(
        f"ALTER TABLE {_TABLE} ADD CONSTRAINT {_FK} "
        "FOREIGN KEY (run_id) REFERENCES control.runs (id)"
    )
