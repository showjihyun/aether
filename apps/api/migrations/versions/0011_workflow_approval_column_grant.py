"""`control.workflow_approvals` - worker 역할의 SELECT 를 열 단위로 좁힌다

Revision ID: 0011
Revises: 0010
Create Date: 2026-10-17

(spec 0005 2.6 개정 5, C-4 - 사람 결정: 0008 docstring 이 남긴 "열 단위 GRANT 로 더 좁히는
선택지" 를 실행한다)

> **이 마이그레이션은 권한을 줄이기만 합니다.** 넓히는 문장이 없습니다.

**왜 좁히는가.** 최소 권한입니다. 0008 은 `aether_data` 에 표 단위
`GRANT SELECT ON control.workflow_approvals` 를 주었고,
그 권한은 `approved_by`(승인 **주체**의 id)와
`note`(사람이 쓴 메모)까지 읽게 합니다. 그런데 실행기는 그 둘을 판정에 쓰지 않습니다 - 엔진은
"이 노드 실행에 승인이 저장돼 있다" 만 압니다(spec 2.6 개정 5, C-4: 승인자 권한 모델은 만들지 않고,
도메인 값 객체 `Approval` 에는 승인 주체 필드가 없습니다). 쓰지 않는 열은 읽을 수 없게 두는 것이
맞습니다: worker 가 침해돼도 승인 주체와 메모는 새지 않고, 나중에 누가 어댑터에 `approved_by` 를
추가해도 DB 가 거부합니다(설계가 코드 리뷰에만 기대지 않습니다).

**무엇을 읽는가.** 실행기 쪽 SQL 이 참조하는 열은 정확히 셋입니다
(참조 = SELECT 목록·JOIN·WHERE 모두;
PostgreSQL 은 쿼리가 *참조하는* 모든 열에 열 권한을 요구합니다).

| 열 | 참조하는 곳 |
| --- | --- |
| `node_execution_id` | `packages/workflow/.../db/approval_reader.py` (SELECT, JOIN, WHERE),
  `apps/worker/.../db/parked_workflow_finder.py` `ready_to_resume` (JOIN) |
| `approved_at` | `approval_reader.py` (SELECT) |
| `workflow_run_id` | `approval_reader.py` (JOIN 조건: 다른 Run 의 id 로 심어진 승인을 믿지
  않는 두 번째 방어선), `parked_workflow_finder.py` (JOIN) |

> 0008 docstring 은 "`node_execution_id`·`approved_at`" 둘이라고 적었습니다. 어댑터의 JOIN 이
> `workflow_run_id` 도 참조하므로 실제 목록은 셋입니다.
> `id` 는 어느 쪽도 참조하지 않아 주지 않습니다.

`approved_by`·`note`·`id` 는 주지 않습니다.

**`SELECT *` 는 거부됩니다.** PostgreSQL 은 열 단위 GRANT 만 가진 역할의 `SELECT *` (모든 열로
확장됨)를 permission denied 로 거부합니다. 실행기 어댑터와 finder 는 `SELECT *` 를 쓰지 않고 열을
이름으로 적습니다(grep 으로 확인했고 통합 테스트가 두 SQL 을 그대로 실행합니다). 앞으로 이 표를
읽는 worker 쪽 코드는 열을 이름으로 적어야 하고, 허용 목록 밖의 열을 참조하면 깨집니다 - 권한을
넓혀 맞추지 말고 그 코드가 정말 그 열을 필요로 하는지 먼저 묻습니다.

**쓰기 권한은 그대로 없습니다**(INSERT·UPDATE·DELETE 불가, 0008). `aether_control` 에는 바뀌는
권한이 없습니다(표 단위 전부 그대로).

**downgrade()** 는 열 단위 GRANT 를 REVOKE 하고 0008 의 표 단위 SELECT 를 되돌립니다.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0011"
down_revision: str | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_DATA_ROLE = "aether_data"
_TABLE = "control.workflow_approvals"
# 실행기가 참조하는 열의 전부(위 docstring 표). `approved_by`·`note`·`id` 는 넣지 않는다.
_READ_COLUMNS = ("workflow_run_id", "node_execution_id", "approved_at")


def upgrade() -> None:
    op.execute(f"REVOKE SELECT ON {_TABLE} FROM {_DATA_ROLE}")
    columns = ", ".join(_READ_COLUMNS)
    op.execute(f"GRANT SELECT ({columns}) ON {_TABLE} TO {_DATA_ROLE}")


def downgrade() -> None:
    columns = ", ".join(_READ_COLUMNS)
    op.execute(f"REVOKE SELECT ({columns}) ON {_TABLE} FROM {_DATA_ROLE}")
    op.execute(f"GRANT SELECT ON {_TABLE} TO {_DATA_ROLE}")
