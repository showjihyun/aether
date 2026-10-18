"""D-17 (MVP-2d): `stream` 의 종결 조각이 `complete` 와 같은 `finish_reason`·`usage` 를 든다.

`model.completed {finish_reason, usage}` 는 스트림으로 바뀐 뒤에도 글자 하나 달라지면
안 되므로, 두 경로가 같은 종결 정보를 준다는 것을 어댑터 층에서 고정합니다.
"""

from __future__ import annotations

import json

import httpx
from aether_runtime.adapters.outbound.model_gateway.fake import FakeModelGateway
from aether_runtime.adapters.outbound.model_gateway.openai_compatible import (
    OpenAICompatibleGateway,
)
from aether_runtime.application.ports.outbound.model_gateway import (
    ModelRequest,
    ModelResponse,
)
from aether_runtime.domain.run import Message

_REQUEST = ModelRequest(messages=[Message(role="user", content="hi")])


def _sse(chunks: list[dict[str, object]]) -> str:
    return "".join(f"data: {json.dumps(c)}\n\n" for c in chunks) + "data: [DONE]\n\n"


def _openai(transport: httpx.MockTransport) -> OpenAICompatibleGateway:
    return OpenAICompatibleGateway(base_url="http://llm.test/v1", model_id="m", transport=transport)


def _sse_response(chunks: list[dict[str, object]]) -> httpx.Response:
    return httpx.Response(200, content=_sse(chunks), headers={"content-type": "text/event-stream"})


def test_fake_stream_terminal_delta_carries_finish_reason_and_usage() -> None:
    """D-17: fake `stream` 의 `done=True` 조각이 응답의 finish_reason·usage 를 든다."""
    response = ModelResponse(
        text="a b", finish_reason="length", usage={"prompt_tokens": 3, "completion_tokens": 2}
    )
    gateway = FakeModelGateway([response, response])

    final = list(gateway.stream(_REQUEST))[-1]
    completed = gateway.complete(_REQUEST)

    assert final.done is True
    assert final.finish_reason == "length"
    assert final.usage == {"prompt_tokens": 3, "completion_tokens": 2}
    assert (final.finish_reason, final.usage) == (completed.finish_reason, completed.usage)


def test_fake_stream_non_terminal_deltas_carry_no_terminal_info() -> None:
    """D-17: 종결 정보는 `done=True` 조각에만 있다."""
    gateway = FakeModelGateway([ModelResponse(text="a b", finish_reason="stop", usage={"x": 1})])

    deltas = list(gateway.stream(_REQUEST))

    assert all(d.finish_reason is None and d.usage is None for d in deltas[:-1])


def test_openai_stream_reads_finish_reason_and_usage_from_chunks() -> None:
    """D-17: finish_reason 은 마지막 choices 청크, usage 는 choices 가 빈 청크에서 온다."""

    def handler(req: httpx.Request) -> httpx.Response:
        return _sse_response(
            [
                {"choices": [{"delta": {"content": "he"}, "finish_reason": None}]},
                {"choices": [{"delta": {"content": "y"}, "finish_reason": "length"}]},
                {"choices": [], "usage": {"prompt_tokens": 5, "completion_tokens": 2}},
            ]
        )

    deltas = list(_openai(httpx.MockTransport(handler)).stream(_REQUEST))

    assert [d.text for d in deltas if d.text] == ["he", "y"]
    assert deltas[-1].done is True
    assert deltas[-1].finish_reason == "length"
    assert deltas[-1].usage == {"prompt_tokens": 5, "completion_tokens": 2}


def test_openai_stream_without_usage_and_finish_reason_defaults() -> None:
    """D-17: 서버가 usage 를 안 주면 None, finish_reason 이 없으면 complete 와 같은 "stop"
    이고 예외가 없다."""

    def handler(req: httpx.Request) -> httpx.Response:
        return _sse_response([{"choices": [{"delta": {"content": "hey"}}]}])

    deltas = list(_openai(httpx.MockTransport(handler)).stream(_REQUEST))

    assert deltas[-1].done is True
    assert deltas[-1].finish_reason == "stop"
    assert deltas[-1].usage is None


def test_stream_request_asks_for_usage_but_complete_request_does_not() -> None:
    """D-17: `stream_options.include_usage` 는 스트림 요청에만 있다."""
    bodies: list[dict[str, object]] = []

    def handler(req: httpx.Request) -> httpx.Response:
        body = json.loads(req.content)
        bodies.append(body)
        if body["stream"]:
            return _sse_response([{"choices": [{"delta": {"content": "x"}}]}])
        return httpx.Response(
            200,
            json={"choices": [{"message": {"role": "assistant", "content": "x"}}]},
        )

    gateway = _openai(httpx.MockTransport(handler))
    list(gateway.stream(_REQUEST))
    gateway.complete(_REQUEST)

    stream_body, complete_body = bodies
    assert stream_body["stream_options"] == {"include_usage": True}
    assert "stream_options" not in complete_body
