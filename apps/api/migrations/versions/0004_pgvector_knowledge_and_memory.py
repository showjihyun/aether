"""`vector` 확장, Knowledge/Memory 네 표 신설, GRANT (spec 0004 2.8, D-1, D-9, D-10, P3-2a)

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-06

`CREATE EXTENSION IF NOT EXISTS vector` 와 spec 2.8 의 네 표를 더합니다 —
`control.knowledge_sets`(Knowledge 집합의 선언)·`control.knowledge_ingestions`
(적재 **선언**과 상태, `control.runs` 와 같은 모양)·`data.knowledge_chunks`
(적재 실행 부산물: 청크 본문·임베딩·출처)·`data.agent_memory`(Run 이 남긴 경험 —
`knowledge_chunks` 와 **다른 표·다른 인덱스**, R-10).

벡터 열의 차원은 `AETHER_EMBED_DIM` 환경변수(기본 768, spec 2.9)로 결정합니다.
`pgvector` SQLAlchemy 타입을 새 의존성으로 들이지 않고 `vector(N)` 을 raw SQL
`ALTER TABLE ... ADD COLUMN` 으로 붙입니다(0001 의 enum 타입·GRANT 가 raw SQL 을
쓰는 것과 같은 방식) — 이 값은 **마이그레이션을 실행하는 시점**에 고정되므로,
임베딩 모델을 바꿔 차원이 달라지면 **새 마이그레이션**이 필요합니다(C-3, D-9. 기존
벡터와 새 차원이 섞이는 조용한 불일치를 막기 위해 자동 변환은 하지 않습니다).

청크·메모리에 `embed_model_id`·`embed_dim` 을 함께 저장합니다(D-9) — 검색 시점에
질의 임베딩의 모델·차원과 저장된 값이 다르면 애플리케이션 계층이 "재적재를
요구하는 오류" 를 내는 근거입니다(이 마이그레이션은 표만 만들고 그 판정 로직은
P3-2b 범위입니다).

GRANT 는 spec 2.8 의 방향입니다 — `aether_control` 은 `control` 의 새 표 전부,
`aether_data` 는 `data` 의 새 표 전부와 `control` 의 새 표 둘에 **SELECT 만**
(Knowledge 바인딩 이름·적재 상태를 worker 가 읽어야 하므로 — `agent_versions`·
`runs` 에 이미 열려 있는 것과 같은 경계, spec 0001 R-7).

`downgrade()` 는 GRANT/REVOKE → 인덱스/표 DROP(참조 역순) → 확장 DROP 순서입니다.
"""

from __future__ import annotations

import os
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_CONTROL_ROLE = "aether_control"
_DATA_ROLE = "aether_data"

_DEFAULT_EMBED_DIM = 768


def _embed_dim() -> int:
    """spec 2.9: `AETHER_EMBED_DIM` — worker·마이그레이션이 함께 읽습니다. 값이 정수가
    아니면 `ValueError` 로 명확히 실패합니다(조용히 기본값으로 넘어가지 않습니다)."""
    raw = os.environ.get("AETHER_EMBED_DIM")
    if raw is None or raw == "":
        return _DEFAULT_EMBED_DIM
    return int(raw)


def upgrade() -> None:
    dim = _embed_dim()

    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # control.knowledge_sets -- Knowledge 집합의 선언(이름만, spec 2.8).
    op.create_table(
        "knowledge_sets",
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
        sa.UniqueConstraint("name", name="uq_knowledge_sets_name"),
        schema="control",
    )

    # control.knowledge_ingestions -- 적재 선언과 상태(`control.runs` 와 같은 모양, D-4).
    op.create_table(
        "knowledge_ingestions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "knowledge_set_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("control.knowledge_sets.id"),
            nullable=False,
        ),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'queued'")),
        sa.Column(
            "requested_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("started_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("finished_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        schema="control",
    )

    # data.knowledge_chunks -- 적재 실행 부산물(청크 본문·임베딩·출처, worker 가 씁니다).
    op.create_table(
        "knowledge_chunks",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "knowledge_set_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("control.knowledge_sets.id"),
            nullable=False,
        ),
        sa.Column(
            "ingestion_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("control.knowledge_ingestions.id"),
            nullable=False,
        ),
        sa.Column("source_path", sa.Text(), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("embed_model_id", sa.Text(), nullable=False),
        sa.Column("embed_dim", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        schema="data",
    )
    op.execute(f"ALTER TABLE data.knowledge_chunks ADD COLUMN embedding vector({dim}) NOT NULL")
    op.execute(
        "CREATE INDEX ix_knowledge_chunks_embedding_hnsw_cosine "
        "ON data.knowledge_chunks USING hnsw (embedding vector_cosine_ops)"
    )

    # data.agent_memory -- Run 이 종결 시 남긴 경험(spec 2.6). `knowledge_chunks` 와
    # **다른 표·다른 인덱스**입니다(R-10) — 한 쿼리로 합치지 않습니다.
    op.create_table(
        "agent_memory",
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
        sa.Column(
            "run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("control.runs.id"),
            nullable=True,
        ),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("embed_model_id", sa.Text(), nullable=False),
        sa.Column("embed_dim", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        schema="data",
    )
    op.execute(f"ALTER TABLE data.agent_memory ADD COLUMN embedding vector({dim}) NOT NULL")
    op.execute(
        "CREATE INDEX ix_agent_memory_embedding_hnsw_cosine "
        "ON data.agent_memory USING hnsw (embedding vector_cosine_ops)"
    )

    # GRANT: control 의 새 표 둘은 aether_control 전부, aether_data 는 SELECT 만
    # (worker 가 Knowledge 집합 이름·적재 상태를 읽어야 합니다 — agent_versions/runs
    # 와 같은 경계, spec 0001 R-7).
    op.execute(f"GRANT ALL PRIVILEGES ON control.knowledge_sets TO {_CONTROL_ROLE}")
    op.execute(f"GRANT ALL PRIVILEGES ON control.knowledge_ingestions TO {_CONTROL_ROLE}")
    op.execute(f"GRANT SELECT ON control.knowledge_sets TO {_DATA_ROLE}")
    op.execute(f"GRANT SELECT ON control.knowledge_ingestions TO {_DATA_ROLE}")

    # GRANT: data 의 새 표 둘은 aether_data 전부. aether_control 은 여전히 data 에
    # 아무 권한이 없습니다(스키마 단계에서 거부, 0001 R-7 과 같은 경계).
    op.execute(f"GRANT ALL PRIVILEGES ON data.knowledge_chunks TO {_DATA_ROLE}")
    op.execute(f"GRANT ALL PRIVILEGES ON data.agent_memory TO {_DATA_ROLE}")


def downgrade() -> None:
    op.execute(f"REVOKE ALL PRIVILEGES ON data.agent_memory FROM {_DATA_ROLE}")
    op.execute(f"REVOKE ALL PRIVILEGES ON data.knowledge_chunks FROM {_DATA_ROLE}")
    op.execute(f"REVOKE SELECT ON control.knowledge_ingestions FROM {_DATA_ROLE}")
    op.execute(f"REVOKE SELECT ON control.knowledge_sets FROM {_DATA_ROLE}")
    op.execute(f"REVOKE ALL PRIVILEGES ON control.knowledge_ingestions FROM {_CONTROL_ROLE}")
    op.execute(f"REVOKE ALL PRIVILEGES ON control.knowledge_sets FROM {_CONTROL_ROLE}")

    op.execute("DROP INDEX IF EXISTS data.ix_agent_memory_embedding_hnsw_cosine")
    op.drop_table("agent_memory", schema="data")

    op.execute("DROP INDEX IF EXISTS data.ix_knowledge_chunks_embedding_hnsw_cosine")
    op.drop_table("knowledge_chunks", schema="data")

    op.drop_table("knowledge_ingestions", schema="control")
    op.drop_table("knowledge_sets", schema="control")

    op.execute("DROP EXTENSION IF EXISTS vector")
