"""`data.tool_call_audit` 신설, `control.tool_permissions` 신설, GRANT
(spec 0003 2.7, D-2, D-15, C-7, P2-2a)

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-26

Gateway(P2-2b)가 판정마다 남길 감사 기록과, 그 판정이 읽을 허용 목록 표를
더합니다. 둘 다 **선언 vs 실행**의 경계(spec 0003 2.7)를 따릅니다.

- `data.tool_call_audit` 은 호출의 **결과**(누가, 언제, 무엇을, 어떤 판정·결과로)만
  남깁니다. 인자·결과 본문은 넣지 않습니다(R-11, D-12) — 그래서 열에 `arguments`나
  `result` 자유 텍스트가 없고 `result_bytes`(크기)·`error_kind`(종류)만 있습니다.
  쓰는 주체는 worker(`aether_data`)이므로 역할 분리(P0-8)가 유지됩니다 —
  `aether_control` 은 이 표에도 여전히 아무 권한이 없습니다.
- `control.tool_permissions` 은 허용 목록의 **선언**입니다(선언은 `control`).
  쓰는 주체는 `aether_control`(CLI 는 API 프로세스 안에서 돌므로 그 역할로 접속,
  spec D-14)이고, 판정 시점에 이 표를 **읽어야** 하는 주체는 worker(`aether_data`)
  입니다 — 그래서 `aether_data` 에 **SELECT 만** 부여합니다(D-15). INSERT/UPDATE/
  DELETE 는 주지 않습니다 — 정책을 쓰는 것은 여전히 `aether_control` 뿐입니다
  (spec C-7). 이 확대는 P2-4 의 🔒 검토 대상이고 `test_plane_roles.py` 가 범위를
  고정합니다.

`downgrade()` 는 GRANT/REVOKE → 테이블 DROP 순서로 역순입니다(0001·0002 의 패턴과
같습니다).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_CONTROL_ROLE = "aether_control"
_DATA_ROLE = "aether_data"


def upgrade() -> None:
    # control.tool_permissions -- 허용 목록의 선언(spec 2.7). 기본값 deny 를 코드가
    # 판정하고, 이 표는 allow/deny 로 명시된 행만 담습니다(D-14 의 CLI 가 씁니다). PK 는
    # (agent_version_id, server_name, tool_name) 셋의 복합키입니다(spec 개정 4) — MCP 에는
    # 전역 도구 이름공간이 없어 서버가 다르면 같은 이름의 도구가 겹칠 수 있고, server_name
    # 이 PK 에 없으면 "Filesystem 의 read 는 허용, PostgreSQL 의 read 는 금지" 를 표현할 수
    # 없습니다. 감사 표가 이미 server_name 을 담으므로 판정의 신분 기준도 같아야 합니다.
    op.create_table(
        "tool_permissions",
        sa.Column(
            "agent_version_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("control.agent_versions.id"),
            primary_key=True,
        ),
        sa.Column("server_name", sa.Text(), nullable=False, primary_key=True),
        sa.Column("tool_name", sa.Text(), primary_key=True),
        sa.Column("decision", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        schema="control",
    )
    op.execute(
        "ALTER TABLE control.tool_permissions "
        "ADD CONSTRAINT ck_tool_permissions_decision "
        "CHECK (decision IN ('allow', 'deny'))"
    )

    # data.tool_call_audit -- 호출의 실행 부산물(spec 2.7). 인자·결과 본문은 없음(D-12).
    op.create_table(
        "tool_call_audit",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("control.runs.id"),
            nullable=False,
        ),
        sa.Column(
            "agent_version_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("control.agent_versions.id"),
            nullable=False,
        ),
        sa.Column("server_name", sa.Text(), nullable=False),
        sa.Column("tool_name", sa.Text(), nullable=False),
        sa.Column("decision", sa.Text(), nullable=False),
        sa.Column("outcome", sa.Text(), nullable=False),
        sa.Column("result_bytes", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("error_kind", sa.Text(), nullable=True),
        sa.Column(
            "started_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("duration_ms", sa.Integer(), nullable=False, server_default=sa.text("0")),
        schema="data",
    )
    op.execute(
        "ALTER TABLE data.tool_call_audit "
        "ADD CONSTRAINT ck_tool_call_audit_decision "
        "CHECK (decision IN ('allow', 'deny'))"
    )
    op.execute(
        "ALTER TABLE data.tool_call_audit "
        "ADD CONSTRAINT ck_tool_call_audit_outcome "
        "CHECK (outcome IN ('ok', 'error', 'denied'))"
    )

    # GRANT: control.tool_permissions 은 aether_control 이 전부, aether_data 는 SELECT 만
    # (D-15, C-7). aether_control 은 여전히 data 스키마에 아무 권한이 없습니다.
    op.execute(f"GRANT ALL PRIVILEGES ON control.tool_permissions TO {_CONTROL_ROLE}")
    op.execute(f"GRANT SELECT ON control.tool_permissions TO {_DATA_ROLE}")

    # GRANT: data.tool_call_audit 은 append-only 입니다 — 감사 기록은 사후 추적이
    # 목적이므로 기록 주체(aether_data)도 자기 기록을 고치거나 지울 수 없습니다
    # (P2-2a 리뷰. control.agent_versions 의 불변 트리거와 같은 성질, P0-8). `id` 는
    # `gen_random_uuid()` 기본값이라 시퀀스 권한은 필요 없습니다 — INSERT·SELECT 만.
    op.execute(f"GRANT INSERT, SELECT ON data.tool_call_audit TO {_DATA_ROLE}")


def downgrade() -> None:
    op.execute(f"REVOKE INSERT, SELECT ON data.tool_call_audit FROM {_DATA_ROLE}")
    op.execute(f"REVOKE SELECT ON control.tool_permissions FROM {_DATA_ROLE}")
    op.execute(f"REVOKE ALL PRIVILEGES ON control.tool_permissions FROM {_CONTROL_ROLE}")

    op.drop_table("tool_call_audit", schema="data")
    op.drop_table("tool_permissions", schema="control")
