"""spec 0002 2.9, R-5: span 트리 `run -> task -> model.complete`/`tool.run`, 속성
키(`aether.run_id`·`aether.agent_version_id`·`aether.task_id`·`aether.tool.name`·
`aether.model.id`), 프롬프트·응답 본문의 부재.
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from aether_runtime.adapters.outbound.model_gateway.fake import FakeModelGateway
from aether_runtime.adapters.outbound.tools.registry import InMemoryToolRegistry
from aether_runtime.application.ports.outbound.model_gateway import ModelResponse
from aether_runtime.application.ports.outbound.run_declaration_reader import RunDeclaration
from aether_runtime.application.usecases.execute_run import ExecuteRunUseCase
from aether_runtime.domain.run import RunStatus
from aether_runtime.domain.tools import ToolCall

from packages.runtime.tests.fakes import (
    FakeClock,
    FakeEventSink,
    FakeRunDeclarationReader,
    FakeRunStateStore,
    FakeStatusNotifier,
    InMemoryTracer,
)

_PROMPT_INPUT = "2 더하기 2 를 계산기로 계산해줘"
_FINAL_TEXT = "답은 4 입니다."


def _definition() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "system_prompt": "You are a helpful test agent.",
        "model": {"id": "test-model"},
        "tools": ["calculator"],
        "policy": {"timeout_seconds": 120, "max_steps": 8, "model_retries": 0, "tool_retries": 0},
    }


def test_span_tree_is_run_task_model_and_tool_with_string_attributes_and_no_prompt_bodies() -> None:
    run_id = uuid4()
    agent_version_id = uuid4()
    clock = FakeClock()
    store = FakeRunStateStore(clock)
    reader = FakeRunDeclarationReader(
        {
            run_id: RunDeclaration(
                run_id=run_id, agent_version_id=agent_version_id, input=_PROMPT_INPUT
            )
        },
        {agent_version_id: _definition()},
    )
    gateway = FakeModelGateway(
        [
            ModelResponse(
                tool_calls=[
                    ToolCall(id="call_1", name="calculator", arguments={"expression": "2+2"})
                ],
                finish_reason="tool_calls",
            ),
            ModelResponse(text=_FINAL_TEXT, finish_reason="stop"),
        ]
    )
    tracer = InMemoryTracer(trace_id="trace-1")
    usecase = ExecuteRunUseCase(
        store=store,
        declarations=reader,
        gateway=gateway,
        tools=InMemoryToolRegistry(clock),
        events=FakeEventSink(),
        notifier=FakeStatusNotifier(),
        tracer=tracer,
        clock=clock,
        owner="worker-a",
    )

    status = usecase(run_id)

    assert status == RunStatus.SUCCEEDED

    names_and_parents = [(span.name, span.parent) for span in tracer.spans]
    assert names_and_parents[0] == ("run", None)
    assert names_and_parents.count(("task", "run")) == 2
    assert ("model.complete", "task") in names_and_parents
    assert ("tool.run", "task") in names_and_parents

    run_span = tracer.spans[0]
    assert run_span.attributes == {
        "aether.run_id": str(run_id),
        "aether.agent_version_id": str(agent_version_id),
    }

    task_span = next(span for span in tracer.spans if span.name == "task")
    assert task_span.attributes["aether.run_id"] == str(run_id)
    assert task_span.attributes["aether.agent_version_id"] == str(agent_version_id)
    assert "aether.task_id" in task_span.attributes

    tool_span = next(span for span in tracer.spans if span.name == "tool.run")
    assert tool_span.attributes["aether.tool.name"] == "calculator"

    model_span = next(span for span in tracer.spans if span.name == "model.complete")
    assert model_span.attributes["aether.model.id"] == "test-model"

    all_attribute_values = " ".join(
        value for span in tracer.spans for value in span.attributes.values()
    )
    assert _PROMPT_INPUT not in all_attribute_values
    assert _FINAL_TEXT not in all_attribute_values
    assert "2+2" not in all_attribute_values
