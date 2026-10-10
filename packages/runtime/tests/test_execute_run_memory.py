"""spec 0004 2.6, D-5, C-5 (P3-4): `ExecuteRunUseCase` 의 Memory 경계.

- 쓰기: `memory_enabled` 가 참이고 Run 이 `succeeded` 로 종결할 때만, 마지막 assistant
  메시지 본문 그대로 한 건. 켜지 않았거나 실패·취소·타임아웃이면 쓰지 않습니다.
- 쓰기 실패는 Run 을 실패로 만들지 않습니다(Memory 는 부산물).
- 읽기: `ContextCompiler` 에 `agent_id` 를 건네는 것은 `memory_enabled` 인 Agent 뿐입니다.

`MemoryWriter`·`ContextCompiler` outbound 포트에 fake 를 꽂습니다(컨테이너 없음).
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import pytest
from aether_runtime.adapters.outbound.model_gateway.fake import FakeModelGateway
from aether_runtime.application.ports.outbound.model_gateway import ModelError, ModelResponse
from aether_runtime.application.ports.outbound.run_declaration_reader import RunDeclaration
from aether_runtime.application.usecases.execute_run import ExecuteRunUseCase
from aether_runtime.domain.agent import AgentDefinition
from aether_runtime.domain.run import RunStatus

from packages.runtime.tests.fakes import (
    FakeClock,
    FakeContextCompiler,
    FakeEventSink,
    FakeMemoryWriter,
    FakeRunDeclarationReader,
    FakeRunStateStore,
    FakeStatusNotifier,
    FakeToolGateway,
    InMemoryTracer,
)

_OWNER = "worker-test"
_AGENT_ID = uuid4()


def _definition(*, memory_enabled: bool | None) -> dict[str, Any]:
    definition: dict[str, Any] = {
        "schema_version": 1,
        "system_prompt": "You are a memory test agent.",
        "model": {"id": "test-model"},
        "tools": [],
        "policy": {"timeout_seconds": 120, "max_steps": 8, "model_retries": 0, "tool_retries": 0},
    }
    if memory_enabled is not None:
        definition["memory_enabled"] = memory_enabled
    return definition


def _setup(
    *,
    memory_enabled: bool | None,
    scenario: list[ModelResponse | ModelError],
    writer: FakeMemoryWriter | None = None,
    agent_id: UUID | None = _AGENT_ID,
    cancel_requested: bool = False,
) -> tuple[ExecuteRunUseCase, FakeMemoryWriter, FakeContextCompiler, UUID]:
    clock = FakeClock()
    run_id = uuid4()
    agent_version_id = uuid4()
    declarations = {
        run_id: RunDeclaration(
            run_id=run_id,
            agent_version_id=agent_version_id,
            agent_id=agent_id,
            input="remember this",
            cancel_requested_at=datetime(2026, 10, 1, tzinfo=UTC) if cancel_requested else None,
        )
    }
    definitions = {agent_version_id: _definition(memory_enabled=memory_enabled)}
    memory_writer = writer if writer is not None else FakeMemoryWriter()
    compiler = FakeContextCompiler()
    usecase = ExecuteRunUseCase(
        store=FakeRunStateStore(clock),
        declarations=FakeRunDeclarationReader(declarations, definitions),
        gateway=FakeModelGateway(scenario),
        tools=FakeToolGateway({}),
        events=FakeEventSink(),
        notifier=FakeStatusNotifier(),
        tracer=InMemoryTracer(),
        clock=clock,
        owner=_OWNER,
        context_compiler=compiler,
        memory_writer=memory_writer,
    )
    return usecase, memory_writer, compiler, run_id


def _ok(text: str) -> list[ModelResponse | ModelError]:
    return [ModelResponse(text=text, finish_reason="stop")]


def _assert_control_run_writes() -> None:
    """대조군: 같은 조립에서 성공 Run 은 실제로 씁니다 — "쓰지 않음" 단언이 쓰기 경로가
    아예 죽어 있어서 우연히 참인 것이 아님을 보입니다."""
    usecase, writer, _compiler, run_id = _setup(memory_enabled=True, scenario=_ok("control"))
    assert usecase(run_id) == RunStatus.SUCCEEDED
    assert len(writer.calls) == 1


def test_agent_definition_memory_enabled_defaults_to_false() -> None:
    """spec 2.6: 기본값 거짓 — 켜지 않은 Agent 는 아무것도 남기지 않습니다."""
    definition = AgentDefinition.model_validate({"schema_version": 1, "system_prompt": "x"})
    assert definition.memory_enabled is False
    enabled = AgentDefinition.model_validate(
        {"schema_version": 1, "system_prompt": "x", "memory_enabled": True}
    )
    assert enabled.memory_enabled is True


def test_succeeded_run_with_memory_enabled_writes_last_assistant_text_verbatim() -> None:
    """spec 2.6: 마지막 assistant 메시지 본문 그대로 한 건 — 요약·분할 없음."""
    body = "  The launch code is ORCHID-7.\n\nSecond paragraph.  "
    usecase, writer, _compiler, run_id = _setup(memory_enabled=True, scenario=_ok(body))

    status = usecase(run_id)

    assert status == RunStatus.SUCCEEDED
    assert writer.calls == [(_AGENT_ID, run_id, body)]


def test_memory_disabled_agent_writes_nothing() -> None:
    """spec 2.6: memory_enabled 가 거짓(기본)이면 쓰지 않습니다 — 대조로 켠 쪽은 씁니다."""
    on, on_writer, _c, on_run = _setup(memory_enabled=True, scenario=_ok("kept"))
    assert on(on_run) == RunStatus.SUCCEEDED
    assert len(on_writer.calls) == 1

    for flag in (False, None):
        usecase, writer, _compiler, run_id = _setup(memory_enabled=flag, scenario=_ok("dropped"))
        assert usecase(run_id) == RunStatus.SUCCEEDED
        assert writer.calls == []


def test_failed_run_writes_nothing() -> None:
    """spec 2.6: 실패 Run 은 쓰지 않습니다."""
    usecase, writer, _compiler, run_id = _setup(
        memory_enabled=True, scenario=[ModelError("protocol", message="boom")]
    )

    assert usecase(run_id) == RunStatus.FAILED
    assert writer.calls == []
    _assert_control_run_writes()


def test_cancelled_run_writes_nothing() -> None:
    """spec 2.6: 취소된 Run 은 쓰지 않습니다."""
    usecase, writer, _compiler, run_id = _setup(
        memory_enabled=True, scenario=_ok("never used"), cancel_requested=True
    )

    assert usecase(run_id) == RunStatus.CANCELLED
    assert writer.calls == []
    _assert_control_run_writes()


def test_blank_final_text_writes_nothing() -> None:
    """지시 (c): 본문이 비어 있으면 쓰지 않습니다 — 대조: 비지 않으면 씁니다."""
    full, full_writer, _c, full_run = _setup(memory_enabled=True, scenario=_ok("x"))
    full(full_run)
    assert len(full_writer.calls) == 1

    for blank in ("", "   \n"):
        usecase, writer, _compiler, run_id = _setup(memory_enabled=True, scenario=_ok(blank))
        assert usecase(run_id) == RunStatus.SUCCEEDED
        assert writer.calls == []


def test_run_without_agent_id_writes_nothing() -> None:
    """agent_id 를 모르면(선언에 없음) 누구의 기억인지 정할 수 없으므로 쓰지 않습니다."""
    on, on_writer, _c, on_run = _setup(memory_enabled=True, scenario=_ok("kept"))
    on(on_run)
    assert len(on_writer.calls) == 1

    usecase, writer, _compiler, run_id = _setup(
        memory_enabled=True, scenario=_ok("x"), agent_id=None
    )
    assert usecase(run_id) == RunStatus.SUCCEEDED
    assert writer.calls == []


def test_writer_failure_does_not_fail_the_run_and_is_logged(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """spec 2.6, C-5: Memory 는 부산물 — writer 가 던져도 Run 은 succeeded 이고 경고가
    남습니다. 경고에 기억 본문을 남기지 않습니다."""
    secret_body = "TOPSECRET-BODY"
    writer = FakeMemoryWriter(error=RuntimeError("db down"))
    usecase, _w, _compiler, run_id = _setup(
        memory_enabled=True, scenario=_ok(secret_body), writer=writer
    )

    with caplog.at_level(logging.WARNING):
        status = usecase(run_id)

    assert len(writer.calls) == 1  # 시도는 했다
    assert status == RunStatus.SUCCEEDED
    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert warnings, "쓰기 실패는 경고 로그를 남겨야 합니다"
    assert str(run_id) in warnings[0].getMessage()
    assert secret_body not in caplog.text


def test_compiler_receives_agent_id_only_when_memory_enabled() -> None:
    """spec 2.6, P3-4 (b): 읽기 쪽 — memory_enabled 인 Agent 만 agent_id 가 건네집니다."""
    on, _w, on_compiler, on_run = _setup(memory_enabled=True, scenario=_ok("a"))
    on(on_run)
    assert on_compiler.calls[0].agent_id == _AGENT_ID

    off, _w2, off_compiler, off_run = _setup(memory_enabled=False, scenario=_ok("a"))
    off(off_run)
    assert off_compiler.calls[0].agent_id is None
