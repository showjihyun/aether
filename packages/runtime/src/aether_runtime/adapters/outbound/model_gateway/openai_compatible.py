"""spec 0002 2.5, D-19 (P1-3): `OpenAICompatibleGateway` — 로컬 LLM 서버(Ollama 등)의
`/v1/chat/completions`, `/v1/embeddings` 를 부릅니다. **`httpx` 는 이 파일에만**
있습니다(AR-5) — 벤더 SDK 는 쓰지 않습니다.

thinking(D-19): Qwen3.8 계열은 기본이 thinking 이라 응답에 `reasoning_content`(또는
`<think>…</think>` 블록)가 옵니다. 이 어댑터는 그것을 `ModelResponse.reasoning`/
`ModelDelta.reasoning` 으로 분리하고 `text` 에는 남기지 않습니다. `thinking=False`
(기본)이면 요청 JSON 에 `"think": false` 를 함께 보냅니다(Ollama 옵션 — 다른
OpenAI-호환 서버는 모르는 필드를 무시합니다). `reasoning` 은 어디에도 로그로
남기지 않습니다(이 모듈에 로그 자체가 없습니다, C-8).
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

import httpx

from aether_runtime.application.ports.outbound.model_gateway import (
    ModelDelta,
    ModelError,
    ModelRequest,
    ModelResponse,
    ToolSchema,
)
from aether_runtime.domain.run import Message
from aether_runtime.domain.tools import ToolCall

_THINK_BLOCK_RE = re.compile(r"<think>(.*?)</think>", re.DOTALL)


def _split_think_block(content: str) -> tuple[str, str | None]:
    """`<think>…</think>` 블록을 떼어 `(text, reasoning)` 으로 돌려줍니다. 블록이
    없으면 `reasoning` 은 `None`."""
    matches = _THINK_BLOCK_RE.findall(content)
    if not matches:
        return content, None
    text = _THINK_BLOCK_RE.sub("", content).strip()
    reasoning = "".join(matches).strip()
    return text, reasoning


def _message_payload(message: Message) -> dict[str, Any]:
    payload: dict[str, Any] = {"role": message.role, "content": message.content}
    if message.tool_call_id is not None:
        payload["tool_call_id"] = message.tool_call_id
    return payload


def _tool_payload(tool: ToolSchema) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.description,
            "parameters": tool.input_schema,
        },
    }


def _parse_usage(raw: object) -> dict[str, int] | None:
    if not isinstance(raw, dict):
        return None
    usage = {key: value for key, value in raw.items() if isinstance(value, int)}
    return usage or None


def _parse_tool_calls(raw: list[dict[str, Any]]) -> list[ToolCall]:
    tool_calls: list[ToolCall] = []
    for entry in raw:
        function = entry.get("function") or {}
        raw_arguments = function.get("arguments") or "{}"
        try:
            arguments = json.loads(raw_arguments)
        except json.JSONDecodeError as exc:
            raise ModelError(
                kind="protocol", message=f"invalid tool_call arguments JSON: {exc}"
            ) from exc
        tool_calls.append(
            ToolCall(id=entry.get("id", ""), name=function.get("name", ""), arguments=arguments)
        )
    return tool_calls


def _parse_message(message: dict[str, Any]) -> tuple[str, str | None, list[ToolCall]]:
    content = message.get("content") or ""
    text, think_reasoning = _split_think_block(content)
    reasoning = message.get("reasoning_content") or message.get("reasoning") or think_reasoning
    tool_calls = _parse_tool_calls(message.get("tool_calls") or [])
    return text, reasoning, tool_calls


@dataclass
class _ToolCallBuffer:
    """스트리밍 중 index 로 흩어져 오는 `delta.tool_calls` 조각을 모읍니다."""

    id: str = ""
    name: str = ""
    arguments: str = ""


class OpenAICompatibleGateway:
    """`ModelGateway` 포트의 OpenAI-호환 HTTP 구현(spec 0002 2.5)."""

    def __init__(
        self,
        base_url: str,
        model_id: str,
        api_key: str | None = None,
        thinking: bool = False,
        timeout_seconds: float = 60.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._model_id = model_id
        self._thinking = thinking
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else None
        self._client = httpx.Client(
            base_url=base_url,
            timeout=timeout_seconds,
            headers=headers,
            transport=transport,
        )

    def _request_body(self, request: ModelRequest, *, stream: bool) -> dict[str, Any]:
        body: dict[str, Any] = {
            "model": request.model_id or self._model_id,
            "messages": [_message_payload(message) for message in request.messages],
            "stream": stream,
        }
        if request.tools:
            body["tools"] = [_tool_payload(tool) for tool in request.tools]
        if not self._thinking:
            body["think"] = False
        return body

    def complete(self, request: ModelRequest) -> ModelResponse:
        body = self._request_body(request, stream=False)
        data = self._post_json("/chat/completions", body, timeout=request.timeout_seconds)
        choices = data.get("choices") or []
        if not choices:
            raise ModelError(kind="protocol", message="response has no choices")
        choice = choices[0]
        text, reasoning, tool_calls = _parse_message(choice.get("message") or {})
        return ModelResponse(
            text=text,
            tool_calls=tool_calls,
            reasoning=reasoning,
            finish_reason=choice.get("finish_reason") or "stop",
            usage=_parse_usage(data.get("usage")),
        )

    def stream(self, request: ModelRequest) -> Iterator[ModelDelta]:
        body = self._request_body(request, stream=True)
        buffers: dict[int, _ToolCallBuffer] = {}
        stream_kwargs: dict[str, Any] = {"json": body}
        if request.timeout_seconds is not None:
            stream_kwargs["timeout"] = request.timeout_seconds
        try:
            with self._client.stream("POST", "/chat/completions", **stream_kwargs) as response:
                if response.status_code >= 400:
                    response.read()
                    raise ModelError(
                        kind="http", status=response.status_code, message=response.text
                    )
                for line in response.iter_lines():
                    if not line or not line.startswith("data:"):
                        continue
                    payload = line[len("data:") :].strip()
                    if payload == "[DONE]":
                        break
                    try:
                        chunk = json.loads(payload)
                    except json.JSONDecodeError as exc:
                        raise ModelError(
                            kind="protocol", message=f"invalid SSE chunk: {exc}"
                        ) from exc
                    yield from self._deltas_from_chunk(chunk, buffers)
        except httpx.TimeoutException as exc:
            raise ModelError(kind="timeout", message=str(exc)) from exc
        except httpx.HTTPError as exc:
            raise ModelError(kind="protocol", message=str(exc)) from exc

        for index in sorted(buffers):
            buffer = buffers[index]
            try:
                arguments = json.loads(buffer.arguments or "{}")
            except json.JSONDecodeError as exc:
                raise ModelError(
                    kind="protocol", message=f"invalid tool_call arguments JSON: {exc}"
                ) from exc
            tool_call = ToolCall(id=buffer.id, name=buffer.name, arguments=arguments)
            yield ModelDelta(tool_call=tool_call)

        yield ModelDelta(done=True)

    def _deltas_from_chunk(
        self, chunk: dict[str, Any], buffers: dict[int, _ToolCallBuffer]
    ) -> Iterator[ModelDelta]:
        choices = chunk.get("choices") or []
        if not choices:
            return
        delta = choices[0].get("delta") or {}

        content = delta.get("content")
        if content:
            text, think_reasoning = _split_think_block(content)
            if think_reasoning:
                yield ModelDelta(reasoning=think_reasoning)
            if text:
                yield ModelDelta(text=text)

        reasoning_content = delta.get("reasoning_content") or delta.get("reasoning")
        if reasoning_content:
            yield ModelDelta(reasoning=reasoning_content)

        for entry in delta.get("tool_calls") or []:
            index = entry.get("index", 0)
            buffer = buffers.setdefault(index, _ToolCallBuffer())
            if entry.get("id"):
                buffer.id = entry["id"]
            function = entry.get("function") or {}
            if function.get("name"):
                buffer.name = function["name"]
            if function.get("arguments"):
                buffer.arguments += function["arguments"]

    def embed(self, texts: list[str]) -> list[list[float]]:
        data = self._post_json("/embeddings", {"model": self._model_id, "input": texts})
        entries = data.get("data") or []
        if len(entries) != len(texts):
            raise ModelError(
                kind="protocol",
                message=f"expected {len(texts)} embeddings, got {len(entries)}",
            )
        ordered = sorted(entries, key=lambda entry: entry.get("index", 0))
        return [entry["embedding"] for entry in ordered]

    def _post_json(
        self, path: str, body: dict[str, Any], *, timeout: float | None = None
    ) -> dict[str, Any]:
        try:
            if timeout is not None:
                response = self._client.post(path, json=body, timeout=timeout)
            else:
                response = self._client.post(path, json=body)
        except httpx.TimeoutException as exc:
            raise ModelError(kind="timeout", message=str(exc)) from exc
        except httpx.HTTPError as exc:
            raise ModelError(kind="protocol", message=str(exc)) from exc
        if response.status_code >= 400:
            raise ModelError(kind="http", status=response.status_code, message=response.text)
        try:
            result: dict[str, Any] = response.json()
        except ValueError as exc:
            raise ModelError(kind="protocol", message=f"invalid JSON response: {exc}") from exc
        return result
