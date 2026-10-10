"""spec 0004 R-3 (P3-1): `ExecuteRunUseCase` 가 모델을 부르기 전에
`ContextCompiler` 포트를 지나는지(직접 조립하지 않는지)를 outbound 포트 fake 로
증명합니다. `packages/context` 의 조립 규칙 자체(R-1, R-2)는
`packages/context/tests/test_compile_context.py` 가 증명하므로, 여기서는
"Executor 가 그 포트를 실제로 부르고 그 결과를 모델 요청에 쓰는가" 만 봅니다.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

from aether_runtime.adapters.outbound.model_gateway.fake import FakeModelGateway
from aether_runtime.application.ports.outbound.model_gateway import ModelResponse
from aether_runtime.application.ports.outbound.run_declaration_reader import RunDeclaration
from aether_runtime.application.usecases.execute_run import ExecuteRunUseCase
from aether_runtime.domain.run import RunStatus

from packages.runtime.tests.fakes import (
    FakeClock,
    FakeContextCompiler,
    FakeEventSink,
    FakeRunDeclarationReader,
    FakeRunStateStore,
    FakeStatusNotifier,
    FakeTool,
    FakeToolGateway,
    InMemoryTracer,
)

_OWNER = "worker-test"
_SYSTEM_PROMPT = "You are a context-compiled test agent."


def _definition(
    context_budget_tokens: int | None = None,
    knowledge: list[str] | None = None,
    knowledge_top_k: int | None = None,
) -> dict[str, Any]:
    definition: dict[str, Any] = {
        "schema_version": 1,
        "system_prompt": _SYSTEM_PROMPT,
        "model": {"id": "test-model"},
        "tools": [],
        "policy": {"timeout_seconds": 120, "max_steps": 8, "model_retries": 0, "tool_retries": 0},
    }
    if context_budget_tokens is not None:
        definition["context_budget_tokens"] = context_budget_tokens
    if knowledge is not None:
        definition["knowledge"] = knowledge
    if knowledge_top_k is not None:
        definition["knowledge_top_k"] = knowledge_top_k
    return definition


def _setup(
    *,
    context_budget_tokens: int | None = None,
    knowledge: list[str] | None = None,
    knowledge_top_k: int | None = None,
) -> tuple[ExecuteRunUseCase, FakeContextCompiler, FakeModelGateway, UUID]:
    clock = FakeClock()
    store = FakeRunStateStore(clock)
    declarations: dict[UUID, RunDeclaration] = {}
    definitions: dict[UUID, dict[str, Any]] = {}
    run_id = uuid4()
    agent_version_id = uuid4()
    declarations[run_id] = RunDeclaration(
        run_id=run_id, agent_version_id=agent_version_id, input="do the thing"
    )
    definitions[agent_version_id] = _definition(
        context_budget_tokens=context_budget_tokens,
        knowledge=knowledge,
        knowledge_top_k=knowledge_top_k,
    )
    reader = FakeRunDeclarationReader(declarations, definitions)
    events = FakeEventSink()
    notifier = FakeStatusNotifier()
    tracer = InMemoryTracer()
    gateway = FakeModelGateway([ModelResponse(text="done", finish_reason="stop")])
    compiler = FakeContextCompiler()
    tools = FakeToolGateway({"calculator": FakeTool(name="calculator")})
    usecase = ExecuteRunUseCase(
        store=store,
        declarations=reader,
        gateway=gateway,
        tools=tools,
        events=events,
        notifier=notifier,
        tracer=tracer,
        clock=clock,
        owner=_OWNER,
        context_compiler=compiler,
    )
    return usecase, compiler, gateway, run_id


def test_execute_run_calls_context_compiler_before_model_with_definition_budget() -> None:
    usecase, compiler, gateway, run_id = _setup(context_budget_tokens=4096)

    status = usecase(run_id)

    assert status == RunStatus.SUCCEEDED
    assert len(compiler.calls) == 1
    call = compiler.calls[0]
    assert call.system_prompt == _SYSTEM_PROMPT
    assert call.budget_tokens == 4096
    assert call.conversation[0].role == "user"
    assert call.conversation[0].content == "do the thing"

    # 모델에 실제로 보낸 messages 는 compiler 가 돌려준 것이어야 합니다 — 첫 메시지가
    # system (compiler 가 붙인 것) 이어야 합니다. Executor 가 직접 system 을 붙이면
    # fake 가 붙인 것과 **중복**됩니다.
    sent = gateway.calls[0].messages
    assert sent[0].role == "system"
    assert sent[0].content == _SYSTEM_PROMPT
    assert sum(1 for m in sent if m.role == "system") == 1


def test_execute_run_uses_default_budget_when_definition_has_none() -> None:
    usecase, compiler, _gateway, run_id = _setup(context_budget_tokens=None)

    usecase(run_id)

    assert compiler.calls[0].budget_tokens == 8192


def test_execute_run_passes_definition_knowledge_and_top_k_to_compiler() -> None:
    """spec 0004 D-5 (P3-3): `definition.knowledge`·`knowledge_top_k` 가 그대로
    `ContextCompiler.compile` 에 건네집니다 — Executor 가 직접 검색하지 않고
    포트를 지납니다(R-3 과 같은 경계)."""
    usecase, compiler, _gateway, run_id = _setup(knowledge=["docs", "faq"], knowledge_top_k=3)

    usecase(run_id)

    assert compiler.calls[0].knowledge_sets == ("docs", "faq")
    assert compiler.calls[0].knowledge_top_k == 3


def test_execute_run_uses_default_knowledge_top_k_when_definition_has_none() -> None:
    """spec D-5: `knowledge_top_k` 가 `None` 이면 `KnowledgeStore.DEFAULT_TOP_K`(5)."""
    usecase, compiler, _gateway, run_id = _setup(knowledge=["docs"], knowledge_top_k=None)

    usecase(run_id)

    assert compiler.calls[0].knowledge_top_k == 5


def test_execute_run_passes_empty_knowledge_sets_when_definition_has_none() -> None:
    usecase, compiler, _gateway, run_id = _setup()

    usecase(run_id)

    assert compiler.calls[0].knowledge_sets == ()
