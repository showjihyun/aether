"""spec 0004 2.5, D-5, D-8, R-8, R-9 (P3-3): 적재된 사실을 묻는 Run 이 **출처와
함께** 답하는 전체 경로 — pgvector testcontainer + 실제 `aether_context` 조립
(`CompileContextUseCase` + `PostgresKnowledgeSearch`) + 실제 `AetherContextCompiler`
+ 실제 `ExecuteRunUseCase`. 모델만 fake 입니다(네트워크 없음).

판정: fake 모델이 받은 요청에서 Knowledge 블록이 `trust=untrusted` + 출처를
달고 있고, system 메시지에 섞이지 않습니다(R-8). `knowledge` 바인딩이 없으면
같은 집합에 사실이 있어도 검색되지 않습니다(R-9).
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import psycopg
import pytest
from aether_context.adapters.outbound.connector.filesystem import FilesystemConnector
from aether_context.adapters.outbound.indexer.fixed_size import FixedSizeIndexer
from aether_context.adapters.outbound.knowledge_search.postgres import PostgresKnowledgeSearch
from aether_context.adapters.outbound.knowledge_store.postgres import PostgresKnowledgeStore
from aether_context.adapters.outbound.token_counter.char_approx import CharApproxTokenCounter
from aether_context.application.ports.inbound.ingest_knowledge import IngestKnowledgeRequest
from aether_context.application.usecases.compile_context import CompileContextUseCase
from aether_context.application.usecases.ingest_knowledge import IngestKnowledgeUseCase
from aether_runtime.adapters.outbound.context_compiler.aether_context import AetherContextCompiler
from aether_runtime.adapters.outbound.model_gateway.fake import FakeModelGateway
from aether_runtime.application.ports.outbound.model_gateway import ModelResponse
from aether_runtime.application.ports.outbound.run_declaration_reader import RunDeclaration
from aether_runtime.application.usecases.execute_run import ExecuteRunUseCase
from aether_runtime.domain.run import RunStatus

from packages.runtime.tests.fakes import (
    FakeClock,
    FakeEventSink,
    FakeRunDeclarationReader,
    FakeRunStateStore,
    FakeStatusNotifier,
    FakeToolGateway,
    InMemoryTracer,
)

pytestmark = pytest.mark.integration

_EMBED_DIM = 768
_EMBED_MODEL_ID = "test-embed-model"
_OWNER = "worker-test"


class _DeterministicHashEmbedder:
    model_id = _EMBED_MODEL_ID
    dim = _EMBED_DIM

    def embed(self, texts: list[str]) -> list[list[float]]:
        import hashlib
        import math
        import re

        vectors: list[list[float]] = []
        for text in texts:
            vector = [0.0] * self.dim
            for word in re.findall(r"[a-zA-Z]+", text.lower()):
                bucket = int(hashlib.sha256(word.encode("utf-8")).hexdigest(), 16) % self.dim
                vector[bucket] += 1.0
            norm = math.sqrt(sum(v * v for v in vector)) or 1.0
            vectors.append([v / norm for v in vector])
        return vectors


def _insert_knowledge_set(conn: psycopg.Connection, name: str) -> uuid.UUID:
    with conn.cursor() as cur:
        cur.execute("INSERT INTO control.knowledge_sets (name) VALUES (%s) RETURNING id", (name,))
        row = cur.fetchone()
        assert row is not None
        set_id: uuid.UUID = row[0]
    conn.commit()
    return set_id


def _insert_ingestion(
    conn: psycopg.Connection, knowledge_set_id: uuid.UUID, source: str
) -> uuid.UUID:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO control.knowledge_ingestions (knowledge_set_id, source)
            VALUES (%s, %s) RETURNING id
            """,
            (knowledge_set_id, source),
        )
        row = cur.fetchone()
        assert row is not None
        ingestion_id: uuid.UUID = row[0]
    conn.commit()
    return ingestion_id


def _ingest_fact(
    tmp_path: Path,
    admin_connection_factory: Callable[[], psycopg.Connection],
    data_connection_factory: Callable[[], psycopg.Connection],
    set_name: str,
) -> None:
    (tmp_path / "facts.txt").write_text(
        "The secret launch code is ORCHID-7. Keep it confidential.", encoding="utf-8"
    )
    admin_conn = admin_connection_factory()
    try:
        knowledge_set_id = _insert_knowledge_set(admin_conn, set_name)
        ingestion_id = _insert_ingestion(admin_conn, knowledge_set_id, str(tmp_path))
    finally:
        admin_conn.close()

    usecase = IngestKnowledgeUseCase(
        FilesystemConnector(),
        FixedSizeIndexer(chunk_chars=1000, overlap_chars=200),
        _DeterministicHashEmbedder(),
        PostgresKnowledgeStore(data_connection_factory),
    )
    usecase(
        IngestKnowledgeRequest(
            knowledge_set_id=knowledge_set_id, ingestion_id=ingestion_id, source=str(tmp_path)
        )
    )


def _build_execute_run(
    data_connection_factory: Callable[[], psycopg.Connection],
    gateway: FakeModelGateway,
    declarations: dict[UUID, RunDeclaration],
    definitions: dict[UUID, dict[str, Any]],
) -> ExecuteRunUseCase:
    clock = FakeClock()
    store = FakeRunStateStore(clock)
    reader = FakeRunDeclarationReader(declarations, definitions)
    events = FakeEventSink()
    notifier = FakeStatusNotifier()
    tracer = InMemoryTracer()
    tools = FakeToolGateway({})

    knowledge_search = PostgresKnowledgeSearch(
        data_connection_factory, _DeterministicHashEmbedder()
    )
    compile_context = CompileContextUseCase(CharApproxTokenCounter(), knowledge_search)
    context_compiler = AetherContextCompiler(compile_context)

    return ExecuteRunUseCase(
        store=store,
        declarations=reader,
        gateway=gateway,
        tools=tools,
        events=events,
        notifier=notifier,
        tracer=tracer,
        clock=clock,
        owner=_OWNER,
        context_compiler=context_compiler,
    )


def test_run_answers_with_knowledge_block_tagged_untrusted_and_not_mixed_into_system(
    tmp_path: Path,
    admin_connection_factory: Callable[[], psycopg.Connection],
    data_connection_factory: Callable[[], psycopg.Connection],
) -> None:
    set_name = f"facts-{uuid.uuid4()}"
    _ingest_fact(tmp_path, admin_connection_factory, data_connection_factory, set_name)

    run_id = uuid4()
    agent_version_id = uuid4()
    declarations = {
        run_id: RunDeclaration(
            run_id=run_id,
            agent_version_id=agent_version_id,
            input="What is the secret launch code?",
        )
    }
    definitions = {
        agent_version_id: {
            "schema_version": 1,
            "system_prompt": "You are a careful assistant.",
            "model": {"id": "test-model"},
            "tools": [],
            "policy": {
                "timeout_seconds": 120,
                "max_steps": 8,
                "model_retries": 0,
                "tool_retries": 0,
            },
            "knowledge": [set_name],
        }
    }
    gateway = FakeModelGateway([ModelResponse(text="ORCHID-7", finish_reason="stop")])
    execute_run = _build_execute_run(data_connection_factory, gateway, declarations, definitions)

    status = execute_run(run_id)

    assert status == RunStatus.SUCCEEDED
    sent = gateway.calls[0].messages
    assert sent[0].role == "system"
    assert sent[0].content == "You are a careful assistant."  # 섞이지 않음(R-8)

    knowledge_messages = [m for m in sent if "[knowledge " in m.content]
    assert len(knowledge_messages) == 1
    assert "trust=untrusted" in knowledge_messages[0].content
    assert "source=facts.txt" in knowledge_messages[0].content
    assert "ORCHID-7" in knowledge_messages[0].content


def test_run_does_not_search_set_when_not_bound_to_definition(
    tmp_path: Path,
    admin_connection_factory: Callable[[], psycopg.Connection],
    data_connection_factory: Callable[[], psycopg.Connection],
) -> None:
    """spec R-9: 사실이 적재돼 있어도 `definition.knowledge` 에 그 집합 이름이
    없으면 검색되지 않습니다 — Knowledge 블록이 아예 없습니다."""
    set_name = f"facts-{uuid.uuid4()}"
    _ingest_fact(tmp_path, admin_connection_factory, data_connection_factory, set_name)

    run_id = uuid4()
    agent_version_id = uuid4()
    declarations = {
        run_id: RunDeclaration(
            run_id=run_id,
            agent_version_id=agent_version_id,
            input="What is the secret launch code?",
        )
    }
    definitions = {
        agent_version_id: {
            "schema_version": 1,
            "system_prompt": "You are a careful assistant.",
            "model": {"id": "test-model"},
            "tools": [],
            "policy": {
                "timeout_seconds": 120,
                "max_steps": 8,
                "model_retries": 0,
                "tool_retries": 0,
            },
            # knowledge 바인딩 없음 — 적재는 돼 있어도 검색되지 않아야 합니다.
        }
    }
    gateway = FakeModelGateway([ModelResponse(text="I don't know", finish_reason="stop")])
    execute_run = _build_execute_run(data_connection_factory, gateway, declarations, definitions)

    status = execute_run(run_id)

    assert status == RunStatus.SUCCEEDED
    sent = gateway.calls[0].messages
    knowledge_messages = [m for m in sent if "[knowledge " in m.content]
    assert knowledge_messages == []
