"""schemas, tables, immutability trigger, and role grants (spec 2.8, R-7, R-8)

Revision ID: 0001
Revises:
Create Date: 2026-09-10

`control` / `data` 스키마 분리와 `aether_control` / `aether_data` 역할 권한을
전부 이 마이그레이션이 소유합니다. 역할 자체는 클러스터 수준이라
`infra/docker/postgres/init/01-roles.sh` (또는 테스트의 `conftest.py`)가 미리
만들어 둡니다 — 여기서는 그 역할이 존재한다고 가정하고 GRANT 만 합니다. 역할이
없으면 Postgres 가 "role ... does not exist" 로 명확히 실패합니다.

`downgrade()` 는 역순으로 전부 되돌립니다: REVOKE → 트리거/함수 DROP → 테이블
DROP(FK 참조 역순) → enum 타입 DROP → 스키마 DROP.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_CONTROL_ROLE = "aether_control"
_DATA_ROLE = "aether_data"

_RUN_EXECUTION_STATUS_VALUES = (
    "queued",
    "running",
    "waiting",
    "succeeded",
    "failed",
    "cancelled",
    "timed_out",
)
_RUN_EXECUTION_STATUS_TYPE = "run_execution_status"


def upgrade() -> None:
    op.execute("CREATE SCHEMA control")
    op.execute("CREATE SCHEMA data")

    status_values = ", ".join(f"'{value}'" for value in _RUN_EXECUTION_STATUS_VALUES)
    op.execute(f"CREATE TYPE data.{_RUN_EXECUTION_STATUS_TYPE} AS ENUM ({status_values})")

    op.create_table(
        "agents",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("name", name="uq_agents_name"),
        schema="control",
    )

    op.create_table(
        "agent_versions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "agent_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("control.agents.id"),
            nullable=False,
        ),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("definition", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("agent_id", "version", name="uq_agent_versions_agent_id_version"),
        schema="control",
    )
    # Phase 0 은 `definition` 의 내부 형태를 정하지 않고 `schema_version` 키
    # 하나만 요구합니다(spec 2.8). jsonb `?` 는 최상위 키 존재 연산자입니다.
    op.execute(
        "ALTER TABLE control.agent_versions "
        "ADD CONSTRAINT ck_agent_versions_definition_has_schema_version "
        "CHECK (definition ? 'schema_version')"
    )

    op.create_table(
        "api_keys",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("label", sa.Text(), nullable=False),
        sa.Column("key_hash", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("revoked_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.UniqueConstraint("key_hash", name="uq_api_keys_key_hash"),
        schema="control",
    )

    op.create_table(
        "runs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "agent_version_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("control.agent_versions.id"),
            nullable=False,
        ),
        sa.Column(
            "requested_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "requested_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("control.api_keys.id"),
            nullable=True,
        ),
        schema="control",
    )

    op.create_table(
        "run_executions",
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
            "status",
            postgresql.ENUM(
                *_RUN_EXECUTION_STATUS_VALUES,
                name=_RUN_EXECUTION_STATUS_TYPE,
                schema="data",
                create_type=False,
            ),
            nullable=False,
        ),
        # started_at/finished_at 은 실행 생애주기에 따라 나중에 채워집니다 —
        # 전이 규칙은 P1-2 가 소유하고 DB 는 값만 저장합니다(spec 2.8).
        sa.Column("started_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("finished_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column("trace_id", sa.Text(), nullable=True),
        sa.UniqueConstraint("run_id", name="uq_run_executions_run_id"),
        schema="data",
    )

    # 불변 트리거: `agent_versions` 는 앱의 예의가 아니라 DB 제약으로 불변입니다(spec R-8).
    op.execute(
        """
        CREATE FUNCTION control.reject_agent_version_mutation() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION
                'control.agent_versions is immutable: % on agent_version % is not allowed',
                TG_OP, OLD.id;
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER agent_versions_immutable
        BEFORE UPDATE OR DELETE ON control.agent_versions
        FOR EACH ROW EXECUTE FUNCTION control.reject_agent_version_mutation()
        """
    )

    # GRANT: aether_control 은 control 전부, data 는 전혀(USAGE 도 없음) — R-7.
    op.execute(f"GRANT USAGE ON SCHEMA control TO {_CONTROL_ROLE}")
    op.execute(f"GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA control TO {_CONTROL_ROLE}")

    # GRANT: aether_data 는 data 전부 + control.agent_versions/control.runs SELECT 만.
    op.execute(f"GRANT USAGE ON SCHEMA data TO {_DATA_ROLE}")
    op.execute(f"GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA data TO {_DATA_ROLE}")
    op.execute(f"GRANT USAGE ON SCHEMA control TO {_DATA_ROLE}")
    op.execute(f"GRANT SELECT ON control.agent_versions TO {_DATA_ROLE}")
    op.execute(f"GRANT SELECT ON control.runs TO {_DATA_ROLE}")


def downgrade() -> None:
    op.execute(f"REVOKE SELECT ON control.runs FROM {_DATA_ROLE}")
    op.execute(f"REVOKE SELECT ON control.agent_versions FROM {_DATA_ROLE}")
    op.execute(f"REVOKE USAGE ON SCHEMA control FROM {_DATA_ROLE}")
    op.execute(f"REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA data FROM {_DATA_ROLE}")
    op.execute(f"REVOKE USAGE ON SCHEMA data FROM {_DATA_ROLE}")

    op.execute(f"REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA control FROM {_CONTROL_ROLE}")
    op.execute(f"REVOKE USAGE ON SCHEMA control FROM {_CONTROL_ROLE}")

    op.execute("DROP TRIGGER IF EXISTS agent_versions_immutable ON control.agent_versions")
    op.execute("DROP FUNCTION IF EXISTS control.reject_agent_version_mutation()")

    op.drop_table("run_executions", schema="data")
    op.drop_table("runs", schema="control")
    op.drop_table("api_keys", schema="control")
    op.drop_table("agent_versions", schema="control")
    op.drop_table("agents", schema="control")

    op.execute(f"DROP TYPE data.{_RUN_EXECUTION_STATUS_TYPE}")

    op.execute("DROP SCHEMA data")
    op.execute("DROP SCHEMA control")
