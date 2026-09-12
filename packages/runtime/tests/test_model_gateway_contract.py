"""spec 0002 2.5, R-6 (P1-3): `ModelGateway` 포트 계약 — fake 와 OpenAI-호환 어댑터가
같은 케이스를 통과합니다(P0-9 `test_api_key_store_contract.py` 와 같은 형태).

OpenAI-호환 쪽은 `httpx.MockTransport` 로 실제 네트워크 없이 돕니다(R-6 — `api-unit`
은 loopback 외 소켓이 차단된 채 실행됩니다). fake 쪽은 시나리오 주입으로 같은
응답 모양을 냅니다.
"""

from __future__ import annotations

import json

import httpx
import pytest
from aether_runtime.adapters.outbound.model_gateway.fake import FakeModelGateway
from aether_runtime.adapters.outbound.model_gateway.openai_compatible import (
    OpenAICompatibleGateway,
)
from aether_runtime.application.ports.outbound.model_gateway import (
    ModelError,
    ModelGateway,
    ModelRequest,
    ModelResponse,
    ToolSchema,
)
from aether_runtime.domain.run import Message
from aether_runtime.domain.tools import ToolCall

_KINDS = [pytest.param("fake", id="fake"), pytest.param("openai", id="openai")]


def _openai_gateway(transport: httpx.BaseTransport, **kwargs: object) -> OpenAICompatibleGateway:
    return OpenAICompatibleGateway(
        base_url="http://llm.test/v1",
        model_id="qwen-test",
        transport=transport,
        **kwargs,  # type: ignore[arg-type]
    )


def _calculator_tool() -> ToolSchema:
    return ToolSchema(
        name="calculator", description="adds numbers", input_schema={"type": "object"}
    )


def _sse(chunks: list[dict[str, object]]) -> str:
    body = "".join(f"data: {json.dumps(chunk)}\n\n" for chunk in chunks)
    return body + "data: [DONE]\n\n"


@pytest.mark.parametrize("kind", _KINDS)
def test_complete_returns_text_response(kind: str) -> None:
    """spec 0002 2.5: `complete` 텍스트 응답 — fake 와 OpenAI-호환이 같은 계약."""
    request = ModelRequest(messages=[Message(role="user", content="hi")])

    if kind == "fake":
        gateway: ModelGateway = FakeModelGateway(
            [ModelResponse(text="hello there", finish_reason="stop")]
        )
    else:

        def handler(req: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={
                    "choices": [
                        {
                            "message": {"role": "assistant", "content": "hello there"},
                            "finish_reason": "stop",
                        }
                    ]
                },
            )

        gateway = _openai_gateway(httpx.MockTransport(handler))

    response = gateway.complete(request)

    assert response.text == "hello there"
    assert response.finish_reason == "stop"
    assert response.tool_calls == []


@pytest.mark.parametrize("kind", _KINDS)
def test_complete_preserves_tool_call_ids(kind: str) -> None:
    """spec 0002 2.5: 도구 호출 응답의 `tool_calls[].id` 보존."""
    request = ModelRequest(
        messages=[Message(role="user", content="what's 2+2?")],
        tools=[_calculator_tool()],
    )

    if kind == "fake":
        gateway: ModelGateway = FakeModelGateway(
            [
                ModelResponse(
                    tool_calls=[
                        ToolCall(id="call_1", name="calculator", arguments={"a": 2, "b": 2})
                    ],
                    finish_reason="tool_calls",
                )
            ]
        )
    else:

        def handler(req: httpx.Request) -> httpx.Response:
            body = json.loads(req.content)
            assert body["tools"][0]["function"]["name"] == "calculator"
            return httpx.Response(
                200,
                json={
                    "choices": [
                        {
                            "message": {
                                "role": "assistant",
                                "content": None,
                                "tool_calls": [
                                    {
                                        "id": "call_1",
                                        "type": "function",
                                        "function": {
                                            "name": "calculator",
                                            "arguments": json.dumps({"a": 2, "b": 2}),
                                        },
                                    }
                                ],
                            },
                            "finish_reason": "tool_calls",
                        }
                    ]
                },
            )

        gateway = _openai_gateway(httpx.MockTransport(handler))

    response = gateway.complete(request)

    assert len(response.tool_calls) == 1
    assert response.tool_calls[0].id == "call_1"
    assert response.tool_calls[0].name == "calculator"
    assert response.tool_calls[0].arguments == {"a": 2, "b": 2}


@pytest.mark.parametrize("kind", _KINDS)
def test_tool_message_sends_tool_call_id(kind: str) -> None:
    """spec 0002 2.5: `tool` 메시지의 `tool_call_id` 가 요청에 실립니다."""
    request = ModelRequest(
        messages=[
            Message(role="user", content="what's 2+2?"),
            Message(role="assistant", content=""),
            Message(role="tool", content="4", tool_call_id="call_1"),
        ]
    )

    if kind == "fake":
        fake_gateway = FakeModelGateway([ModelResponse(text="It's 4.", finish_reason="stop")])
        fake_gateway.complete(request)
        assert fake_gateway.calls[-1].messages[-1].tool_call_id == "call_1"
        return

    captured: dict[str, object] = {}

    def handler(req: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(req.content)
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {"role": "assistant", "content": "It's 4."},
                        "finish_reason": "stop",
                    }
                ]
            },
        )

    openai_gateway = _openai_gateway(httpx.MockTransport(handler))
    openai_gateway.complete(request)

    body = captured["body"]
    assert isinstance(body, dict)
    tool_message = body["messages"][-1]
    assert tool_message["role"] == "tool"
    assert tool_message["tool_call_id"] == "call_1"


@pytest.mark.parametrize("kind", _KINDS)
def test_stream_assembles_tool_call_chunks_by_index(kind: str) -> None:
    """spec 0002 2.5: tools + stream 청크 조립 — 도구 호출 조각이 index 로 합쳐집니다."""
    request = ModelRequest(
        messages=[Message(role="user", content="2+2?")],
        tools=[_calculator_tool()],
    )

    if kind == "fake":
        gateway: ModelGateway = FakeModelGateway(
            [
                ModelResponse(
                    tool_calls=[
                        ToolCall(id="call_1", name="calculator", arguments={"a": 2, "b": 2})
                    ],
                    finish_reason="tool_calls",
                )
            ]
        )
    else:

        def handler(req: httpx.Request) -> httpx.Response:
            body = json.loads(req.content)
            assert body["stream"] is True
            chunks: list[dict[str, object]] = [
                {
                    "choices": [
                        {
                            "delta": {
                                "tool_calls": [
                                    {
                                        "index": 0,
                                        "id": "call_1",
                                        "type": "function",
                                        "function": {"name": "calculator", "arguments": ""},
                                    }
                                ]
                            },
                            "finish_reason": None,
                        }
                    ]
                },
                {
                    "choices": [
                        {
                            "delta": {
                                "tool_calls": [{"index": 0, "function": {"arguments": '{"a": 2,'}}]
                            },
                            "finish_reason": None,
                        }
                    ]
                },
                {
                    "choices": [
                        {
                            "delta": {
                                "tool_calls": [{"index": 0, "function": {"arguments": ' "b": 2}'}}]
                            },
                            "finish_reason": None,
                        }
                    ]
                },
                {"choices": [{"delta": {}, "finish_reason": "tool_calls"}]},
            ]
            return httpx.Response(
                200, content=_sse(chunks), headers={"content-type": "text/event-stream"}
            )

        gateway = _openai_gateway(httpx.MockTransport(handler))

    deltas = list(gateway.stream(request))

    tool_call_deltas = [d.tool_call for d in deltas if d.tool_call is not None]
    assert len(tool_call_deltas) == 1
    assert tool_call_deltas[0].id == "call_1"
    assert tool_call_deltas[0].name == "calculator"
    assert tool_call_deltas[0].arguments == {"a": 2, "b": 2}
    assert deltas[-1].done is True


@pytest.mark.parametrize("kind", _KINDS)
def test_complete_separates_reasoning_from_text(kind: str) -> None:
    """spec 0002 2.5, D-19: `reasoning` 분리 — `text` 에 `<think>` 가 남지 않습니다."""
    request = ModelRequest(messages=[Message(role="user", content="why?")])

    if kind == "fake":
        gateway: ModelGateway = FakeModelGateway(
            [ModelResponse(text="42", reasoning="because math", finish_reason="stop")]
        )
    else:

        def handler(req: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={
                    "choices": [
                        {
                            "message": {
                                "role": "assistant",
                                "content": "42",
                                "reasoning_content": "because math",
                            },
                            "finish_reason": "stop",
                        }
                    ]
                },
            )

        gateway = _openai_gateway(httpx.MockTransport(handler))

    response = gateway.complete(request)

    assert response.text == "42"
    assert "<think>" not in response.text
    assert response.reasoning == "because math"


@pytest.mark.parametrize("kind", _KINDS)
def test_complete_raises_http_model_error_on_5xx(kind: str) -> None:
    """spec 0002 2.5, R-6: 5xx → `ModelError(kind='http')`."""
    request = ModelRequest(messages=[Message(role="user", content="hi")])

    if kind == "fake":
        gateway: ModelGateway = FakeModelGateway([ModelError(kind="http", status=500)])
    else:

        def handler(req: httpx.Request) -> httpx.Response:
            return httpx.Response(500, text="internal error")

        gateway = _openai_gateway(httpx.MockTransport(handler))

    with pytest.raises(ModelError) as exc_info:
        gateway.complete(request)

    assert exc_info.value.kind == "http"
    if kind == "openai":
        assert exc_info.value.status == 500


@pytest.mark.parametrize("kind", _KINDS)
def test_complete_raises_timeout_model_error(kind: str) -> None:
    """spec 0002 2.5, R-6: 타임아웃 → `ModelError(kind='timeout')`."""
    request = ModelRequest(messages=[Message(role="user", content="hi")])

    if kind == "fake":
        gateway: ModelGateway = FakeModelGateway([ModelError(kind="timeout")])
    else:

        def handler(req: httpx.Request) -> httpx.Response:
            raise httpx.ReadTimeout("timed out", request=req)

        gateway = _openai_gateway(httpx.MockTransport(handler))

    with pytest.raises(ModelError) as exc_info:
        gateway.complete(request)

    assert exc_info.value.kind == "timeout"


@pytest.mark.parametrize("kind", _KINDS)
def test_embed_round_trips_length_and_dimension(kind: str) -> None:
    """spec 0002 2.5: `embed` 왕복 — 길이(입력 개수)·차원(벡터 길이)."""
    texts = ["hello", "world"]

    if kind == "fake":
        gateway: ModelGateway = FakeModelGateway([])
    else:

        def handler(req: httpx.Request) -> httpx.Response:
            body = json.loads(req.content)
            return httpx.Response(
                200,
                json={
                    "data": [
                        {"embedding": [0.1] * 8, "index": index}
                        for index, _ in enumerate(body["input"])
                    ]
                },
            )

        gateway = _openai_gateway(httpx.MockTransport(handler))

    vectors = gateway.embed(texts)

    assert len(vectors) == len(texts)
    assert all(len(vector) == 8 for vector in vectors)
