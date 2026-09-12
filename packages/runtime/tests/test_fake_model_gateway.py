"""spec 0002 2.5 (P1-3): `FakeModelGateway` — 시나리오 소비 순서, 고갈, 호출 기록.

전 테스트와 `smoke` 의 기본 어댑터이므로(2.5), 시나리오가 순서대로 소비되고
고갈되면 `ModelError` 를 내며, 호출 기록(`calls`)이 요청 구조를 그대로 보관하는지를
증명합니다.
"""

from __future__ import annotations

import pytest
from aether_runtime.adapters.outbound.model_gateway.fake import FakeModelGateway
from aether_runtime.application.ports.outbound.model_gateway import (
    ModelError,
    ModelRequest,
    ModelResponse,
)
from aether_runtime.domain.run import Message
from aether_runtime.domain.tools import ToolCall


def _request(text: str = "hi") -> ModelRequest:
    return ModelRequest(messages=[Message(role="user", content=text)])


def test_complete_consumes_scenario_in_order() -> None:
    """spec 0002 2.5: 시나리오는 스크립트된 응답 열을 `complete` 호출 순서대로 소비합니다."""
    gateway = FakeModelGateway(
        [
            ModelResponse(text="first", finish_reason="stop"),
            ModelResponse(text="second", finish_reason="stop"),
        ]
    )

    first = gateway.complete(_request())
    second = gateway.complete(_request())

    assert first.text == "first"
    assert second.text == "second"


def test_complete_raises_model_error_when_scenario_exhausted() -> None:
    """spec 0002 2.5 (plan P1-3 순서 2): 시나리오 고갈 시 `ModelError`."""
    gateway = FakeModelGateway([ModelResponse(text="only", finish_reason="stop")])
    gateway.complete(_request())

    with pytest.raises(ModelError):
        gateway.complete(_request())


def test_complete_raises_scripted_model_error() -> None:
    """spec 0002 2.5: 시나리오 항목이 예외(`ModelError`)이면 그것을 그대로 던집니다."""
    gateway = FakeModelGateway([ModelError(kind="http", status=503)])

    with pytest.raises(ModelError) as exc_info:
        gateway.complete(_request())

    assert exc_info.value.kind == "http"
    assert exc_info.value.status == 503


def test_calls_records_request_structure() -> None:
    """spec 0002 2.5: `calls` 기록 — 테스트가 요청 구조를 단언할 수 있습니다."""
    gateway = FakeModelGateway([ModelResponse(text="ok", finish_reason="stop")])

    gateway.complete(_request("what is 2+2"))

    assert len(gateway.calls) == 1
    assert gateway.calls[0].messages[0].content == "what is 2+2"


def test_stream_yields_deltas_for_tool_call_response() -> None:
    """spec 0002 2.5: `stream` 은 같은 응답을 delta 로 쪼개 냅니다."""
    gateway = FakeModelGateway(
        [
            ModelResponse(
                tool_calls=[ToolCall(id="call_1", name="calculator", arguments={"a": 1})],
                finish_reason="tool_calls",
            )
        ]
    )

    deltas = list(gateway.stream(_request()))

    tool_call_deltas = [d.tool_call for d in deltas if d.tool_call is not None]
    assert len(tool_call_deltas) == 1
    assert tool_call_deltas[0].id == "call_1"
    assert tool_call_deltas[0].name == "calculator"
    assert deltas[-1].done is True


def test_embed_is_deterministic_and_has_eight_dimensions() -> None:
    """spec 0002 2.5: `embed` 는 결정적 벡터(길이 8, 문자열 해시 기반)를 냅니다."""
    gateway = FakeModelGateway([])

    first = gateway.embed(["hello"])
    second = gateway.embed(["hello"])

    assert first == second
    assert len(first[0]) == 8
    assert all(isinstance(value, float) for value in first[0])
