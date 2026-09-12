"""spec 0002 2.5, D-19 (P1-3): OpenAI-호환 어댑터의 thinking 옵션과 reasoning 분리.

Qwen3.8 계열은 기본이 thinking 이라 응답에 `reasoning_content`(또는 `<think>` 블록)가
옵니다. 어댑터는 그것을 `ModelResponse.reasoning` 으로 분리하고 `text` 에는 넣지
않으며, `AETHER_MODEL_THINKING=false`(기본)이면 요청에 `think: false` 를 보냅니다.
"""

from __future__ import annotations

import json

import httpx
from aether_runtime.adapters.outbound.model_gateway.openai_compatible import (
    OpenAICompatibleGateway,
)
from aether_runtime.application.ports.outbound.model_gateway import ModelRequest
from aether_runtime.domain.run import Message


def _gateway(transport: httpx.BaseTransport, *, thinking: bool = False) -> OpenAICompatibleGateway:
    return OpenAICompatibleGateway(
        base_url="http://llm.test/v1",
        model_id="qwen-test",
        thinking=thinking,
        transport=transport,
    )


def _text_response(handler: httpx.MockTransport) -> OpenAICompatibleGateway:
    return _gateway(handler)


def test_thinking_false_sends_think_false_field() -> None:
    """spec 0002 2.5, D-19: `thinking=False`(기본)면 요청 JSON 에 `think: false` 를 보냅니다."""
    captured: dict[str, object] = {}

    def handler(req: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(req.content)
        return httpx.Response(
            200,
            json={
                "choices": [
                    {"message": {"role": "assistant", "content": "ok"}, "finish_reason": "stop"}
                ]
            },
        )

    gateway = _gateway(httpx.MockTransport(handler), thinking=False)
    gateway.complete(ModelRequest(messages=[Message(role="user", content="hi")]))

    body = captured["body"]
    assert isinstance(body, dict)
    assert body["think"] is False


def test_thinking_true_does_not_send_think_false() -> None:
    """spec 0002 2.5, D-19: `thinking=True` 면 `think: false` 를 보내지 않습니다."""
    captured: dict[str, object] = {}

    def handler(req: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(req.content)
        return httpx.Response(
            200,
            json={
                "choices": [
                    {"message": {"role": "assistant", "content": "ok"}, "finish_reason": "stop"}
                ]
            },
        )

    gateway = _gateway(httpx.MockTransport(handler), thinking=True)
    gateway.complete(ModelRequest(messages=[Message(role="user", content="hi")]))

    body = captured["body"]
    assert isinstance(body, dict)
    assert body.get("think") is not False


def test_reasoning_content_field_is_separated() -> None:
    """spec 0002 2.5, D-19: `message.reasoning_content` 는 `ModelResponse.reasoning` 으로."""

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

    gateway = _text_response(httpx.MockTransport(handler))
    response = gateway.complete(ModelRequest(messages=[Message(role="user", content="why")]))

    assert response.text == "42"
    assert response.reasoning == "because math"


def test_think_block_in_content_is_separated() -> None:
    """spec 0002 2.5, D-19: `content` 안의 `<think>…</think>` 블록은 떼어 `reasoning` 에
    붙이고 `text` 에서는 제거합니다."""

    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": "<think>because math</think>42",
                        },
                        "finish_reason": "stop",
                    }
                ]
            },
        )

    gateway = _text_response(httpx.MockTransport(handler))
    response = gateway.complete(ModelRequest(messages=[Message(role="user", content="why")]))

    assert response.text == "42"
    assert "<think>" not in response.text
    assert response.reasoning == "because math"


def test_stream_reasoning_content_delta_is_separated() -> None:
    """spec 0002 2.5: 스트리밍의 `delta.reasoning_content` 도 `reasoning` 델타로 분리됩니다."""

    def handler(req: httpx.Request) -> httpx.Response:
        chunks = [
            {"choices": [{"delta": {"reasoning_content": "because "}, "finish_reason": None}]},
            {"choices": [{"delta": {"reasoning_content": "math"}, "finish_reason": None}]},
            {"choices": [{"delta": {"content": "42"}, "finish_reason": None}]},
            {"choices": [{"delta": {}, "finish_reason": "stop"}]},
        ]
        body = "".join(f"data: {json.dumps(c)}\n\n" for c in chunks) + "data: [DONE]\n\n"
        return httpx.Response(200, content=body, headers={"content-type": "text/event-stream"})

    gateway = _text_response(httpx.MockTransport(handler))
    deltas = list(gateway.stream(ModelRequest(messages=[Message(role="user", content="why")])))

    reasoning = "".join(d.reasoning or "" for d in deltas)
    text = "".join(d.text or "" for d in deltas)
    assert reasoning == "because math"
    assert text == "42"
    assert deltas[-1].done is True
