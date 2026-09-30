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


def test_complete_returns_default_when_scenario_is_empty() -> None:
    """spec 0002 2.5 (P1-5a): `default` 가 있으면 시나리오 소진 뒤 `ModelError` 대신
    그 응답을 계속 돌려줍니다 — compose 의 `AETHER_MODEL_ADAPTER=fake` 가 매 호출마다
    `ModelError` 로 죽지 않게 합니다."""
    default = ModelResponse(text="default answer", finish_reason="stop")
    gateway = FakeModelGateway(default=default)

    first = gateway.complete(_request())
    second = gateway.complete(_request())

    assert first == default
    assert second == default


def test_default_is_used_only_after_scenario_is_exhausted() -> None:
    """spec 0002 2.5: 시나리오가 있으면 먼저 소비하고, 소진된 뒤에만 `default` 로 넘어갑니다."""
    default = ModelResponse(text="fallback", finish_reason="stop")
    gateway = FakeModelGateway(
        [ModelResponse(text="scripted", finish_reason="stop")], default=default
    )

    first = gateway.complete(_request())
    second = gateway.complete(_request())

    assert first.text == "scripted"
    assert second == default


def test_echo_returns_the_last_user_message_with_no_tool_calls() -> None:
    """spec 0002 2.5 (P1-5a): `FakeModelGateway.echo()` — 마지막 `user` 메시지를 그대로
    돌려주는 기본 응답. compose 의 `AETHER_MODEL_ADAPTER=fake` 가 무한히 `succeeded`
    를 만들 수 있게 합니다."""
    gateway = FakeModelGateway.echo()

    response = gateway.complete(_request("hello there"))

    assert response.text == "hello there"
    assert response.tool_calls == []
    assert response.finish_reason == "stop"


def test_echo_calls_a_tool_when_last_user_message_uses_the_tool_call_marker() -> None:
    """spec 0003 R-7 (plan 0003 P2-5): `smoke` 는 실제 모델 없이(fake) Filesystem
    도구 호출을 결정적으로 일으켜야 합니다 — `echo()` 는 마지막 `user` 메시지가
    `TOOL_CALL <name> <json-args>` 형식이면 도구 호출 응답을 돌려줍니다. 마커가
    없는 기존 텍스트 echo 동작(P1-5a)은 그대로입니다."""
    gateway = FakeModelGateway.echo()

    response = gateway.complete(_request('TOOL_CALL read_text_file {"path": "/data/x.txt"}'))

    assert response.finish_reason == "tool_calls"
    assert len(response.tool_calls) == 1
    call = response.tool_calls[0]
    assert call.name == "read_text_file"
    assert call.arguments == {"path": "/data/x.txt"}


def test_echo_returns_tool_result_as_final_text_after_a_tool_message() -> None:
    """spec 0003 R-7: 도구 호출 뒤 `role: tool` 메시지가 붙으면(spec 0002 2.6) 그
    내용을 최종 텍스트로 돌려주어 Run 이 `succeeded` 로 끝날 수 있게 합니다."""
    gateway = FakeModelGateway.echo()
    request = ModelRequest(
        messages=[
            Message(role="user", content="TOOL_CALL echo {}"),
            Message(role="tool", tool_call_id="call_1", content="file contents here"),
        ]
    )

    response = gateway.complete(request)

    assert response.finish_reason == "stop"
    assert response.text == "file contents here"
    assert response.tool_calls == []


def test_embed_is_deterministic_and_has_eight_dimensions() -> None:
    """spec 0002 2.5: `embed` 는 결정적 벡터(길이 8, 문자열 해시 기반)를 냅니다."""
    gateway = FakeModelGateway([])

    first = gateway.embed(["hello"])
    second = gateway.embed(["hello"])

    assert first == second
    assert len(first[0]) == 8
    assert all(isinstance(value, float) for value in first[0])
