"""spec 0004 2.6, R-10, D-8, C-5 (P3-4): Memory 의 전체 경로 — pgvector testcontainer +
실제 `aether_memory`(쓰기·읽기 유스케이스, `PostgresMemoryStore`) + 실제 `aether_context`
조립 + 실제 `ExecuteRunUseCase`. 모델만 fake 입니다(네트워크 없음).

Run 1 이 `succeeded` 로 끝나며 마지막 assistant 본문을 `data.agent_memory` 에 남기고,
Run 2 의 모델 요청에서 그 기억이 `verified=false` 표지를 단 **독립된 메시지**로 들어갑니다
(system 에 섞이지 않고, Knowledge 표지도 아닙니다). `memory_enabled` 가 아닌 Agent 는
남기지도 읽지도 않습니다.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Callable
from typing import Any
from uuid import UUID

import psycopg
import pytest
from aether_context.adapters.outbound.token_counter.char_approx import CharApproxTokenCounter
from aether_context.application.usecases.compile_context import CompileContextUseCase
from aether_memory.adapters.outbound.memory_store.postgres import PostgresMemoryStore
from aether_memory.application.usecases.read_agent_memory import ReadAgentMemoryUseCase
from aether_memory.application.usecases.write_agent_memory import WriteAgentMemoryUseCase
from aether_runtime.adapters.outbound.context_compiler.aether_context import AetherContextCompiler
from aether_runtime.adapters.outbound.model_gateway.fake import FakeModelGateway
from aether_runtime.application.ports.outbound.model_gateway import ModelResponse
from aether_runtime.application.ports.outbound.run_declaration_reader import RunDeclaration
from aether_runtime.application.usecases.execute_run import ExecuteRunUseCase
from aether_runtime.domain.run import RunStatus
from aether_worker.adapters.outbound.memory.reader import MemoryReaderAdapter

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
_OWNER = "worker-test"


class _HashEmbedder:
    model_id = "test-embed-model"
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


def _definition(memory_enabled: bool) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "system_prompt": "You are a careful assistant.",
        "model": {"id": "test-model"},
        "tools": [],
        "policy": {"timeout_seconds": 120, "max_steps": 8, "model_retries": 0, "tool_retries": 0},
        "memory_enabled": memory_enabled,
    }


def _insert_agent_with_version(
    admin_connection_factory: Callable[[], psycopg.Connection], memory_enabled: bool
) -> tuple[UUID, UUID]:
    conn = admin_connection_factory()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO control.agents (name) VALUES (%s) RETURNING id",
                (f"e2e-memory-{uuid.uuid4()}",),
            )
            row = cur.fetchone()
            assert row is not None
            agent_id: UUID = row[0]
            cur.execute(
                "INSERT INTO control.agent_versions (agent_id, version, definition) "
                "VALUES (%s, 1, %s) RETURNING id",
                (agent_id, json.dumps(_definition(memory_enabled))),
            )
            row = cur.fetchone()
            assert row is not None
            version_id: UUID = row[0]
        conn.commit()
    finally:
        conn.close()
    return agent_id, version_id


def _insert_run(
    admin_connection_factory: Callable[[], psycopg.Connection], version_id: UUID, run_input: str
) -> UUID:
    conn = admin_connection_factory()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO control.runs (agent_version_id, input) VALUES (%s, %s) RETURNING id",
                (version_id, run_input),
            )
            row = cur.fetchone()
            assert row is not None
            run_id: UUID = row[0]
        conn.commit()
    finally:
        conn.close()
    return run_id


def _execute(
    data_connection_factory: Callable[[], psycopg.Connection],
    *,
    run_id: UUID,
    agent_id: UUID,
    version_id: UUID,
    run_input: str,
    memory_enabled: bool,
    reply: str,
) -> tuple[RunStatus, FakeModelGateway]:
    clock = FakeClock()
    embedder = _HashEmbedder()
    store = PostgresMemoryStore(data_connection_factory)
    reader = MemoryReaderAdapter(ReadAgentMemoryUseCase(embedder, store))
    compiler = AetherContextCompiler(CompileContextUseCase(CharApproxTokenCounter(), None, reader))
    gateway = FakeModelGateway([ModelResponse(text=reply, finish_reason="stop")])
    declarations = {
        run_id: RunDeclaration(
            run_id=run_id, agent_version_id=version_id, agent_id=agent_id, input=run_input
        )
    }
    execute_run = ExecuteRunUseCase(
        store=FakeRunStateStore(clock),
        declarations=FakeRunDeclarationReader(
            declarations, {version_id: _definition(memory_enabled)}
        ),
        gateway=gateway,
        tools=FakeToolGateway({}),
        events=FakeEventSink(),
        notifier=FakeStatusNotifier(),
        tracer=InMemoryTracer(),
        clock=clock,
        owner=_OWNER,
        context_compiler=compiler,
        memory_writer=WriteAgentMemoryUseCase(embedder, store),
    )
    return execute_run(run_id), gateway


def _count(admin_connection_factory: Callable[[], psycopg.Connection], agent_id: UUID) -> int:
    conn = admin_connection_factory()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM data.agent_memory WHERE agent_id = %s", (agent_id,))
            row = cur.fetchone()
            assert row is not None
            count: int = row[0]
            return count
    finally:
        conn.close()


def test_second_run_sees_first_runs_answer_as_unverified_memory_block(
    admin_connection_factory: Callable[[], psycopg.Connection],
    data_connection_factory: Callable[[], psycopg.Connection],
) -> None:
    agent_id, version_id = _insert_agent_with_version(admin_connection_factory, True)
    run1 = _insert_run(admin_connection_factory, version_id, "what is the launch code")
    status1, _ = _execute(
        data_connection_factory,
        run_id=run1,
        agent_id=agent_id,
        version_id=version_id,
        run_input="what is the launch code",
        memory_enabled=True,
        reply="The launch code is ORCHID-7.",
    )
    assert status1 == RunStatus.SUCCEEDED
    assert _count(admin_connection_factory, agent_id) == 1

    run2 = _insert_run(admin_connection_factory, version_id, "launch code again")
    status2, gateway = _execute(
        data_connection_factory,
        run_id=run2,
        agent_id=agent_id,
        version_id=version_id,
        run_input="launch code again",
        memory_enabled=True,
        reply="ORCHID-7",
    )

    assert status2 == RunStatus.SUCCEEDED
    sent = gateway.calls[0].messages
    assert sent[0].role == "system"
    assert sent[0].content == "You are a careful assistant."  # 섞이지 않음
    memory_messages = [m for m in sent if "[memory " in m.content]
    assert len(memory_messages) == 1
    assert "verified=false" in memory_messages[0].content
    assert "ORCHID-7" in memory_messages[0].content
    assert "[knowledge " not in memory_messages[0].content
    assert "trust=untrusted" not in memory_messages[0].content
    # Run 2 도 succeeded 로 끝났으므로 기억이 하나 더 쌓였다.
    assert _count(admin_connection_factory, agent_id) == 2


def test_agent_without_memory_enabled_neither_writes_nor_reads(
    admin_connection_factory: Callable[[], psycopg.Connection],
    data_connection_factory: Callable[[], psycopg.Connection],
) -> None:
    agent_id, version_id = _insert_agent_with_version(admin_connection_factory, False)
    # 같은 Agent 에 기억이 이미 있더라도(예: 예전에 켜 두었던 경우) 읽지 않습니다.
    seed = WriteAgentMemoryUseCase(_HashEmbedder(), PostgresMemoryStore(data_connection_factory))
    seed.write(agent_id, None, "The launch code is ORCHID-7.")
    run_id = _insert_run(admin_connection_factory, version_id, "launch code")

    status, gateway = _execute(
        data_connection_factory,
        run_id=run_id,
        agent_id=agent_id,
        version_id=version_id,
        run_input="launch code",
        memory_enabled=False,
        reply="I do not know.",
    )

    assert status == RunStatus.SUCCEEDED
    assert not any("[memory " in m.content for m in gateway.calls[0].messages)
    assert _count(admin_connection_factory, agent_id) == 1  # 씨앗 하나뿐

    # 대조군: 같은 Agent·같은 씨앗에서 켠 Run 은 그 기억을 읽습니다 — 위 "읽지 않음" 이
    # 씨앗이 없거나 읽기 경로가 죽어서 참인 것이 아님을 보입니다.
    control_run = _insert_run(admin_connection_factory, version_id, "launch code")
    _status, control_gateway = _execute(
        data_connection_factory,
        run_id=control_run,
        agent_id=agent_id,
        version_id=version_id,
        run_input="launch code",
        memory_enabled=True,
        reply="ORCHID-7",
    )
    assert any("[memory " in m.content for m in control_gateway.calls[0].messages)
