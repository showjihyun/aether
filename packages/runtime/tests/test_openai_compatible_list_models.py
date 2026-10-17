"""spec 0006 R-9, D-5 (MVP-3): `OpenAICompatibleGateway.list_models` - 서버에 **이미 있는**
모델 id 를 `GET /models` 로 묻습니다. 워커가 시작 지점에서 "볼륨에 모델이 있는가" 를 판정하는
재료입니다(받지는 않습니다 - DP-4)."""

from __future__ import annotations

import httpx
import pytest
from aether_runtime.adapters.outbound.model_gateway.openai_compatible import (
    OpenAICompatibleGateway,
)
from aether_runtime.application.ports.outbound.model_gateway import ModelError


def _gateway(transport: httpx.BaseTransport) -> OpenAICompatibleGateway:
    return OpenAICompatibleGateway(
        base_url="http://llm.test/v1", model_id="qwen-test", transport=transport
    )


def test_list_models_returns_ids_from_get_models() -> None:
    """spec 0006 R-9: `GET {base}/models` 의 `data[].id` 를 순서대로 돌려준다."""
    seen: list[tuple[str, str]] = []

    def handler(req: httpx.Request) -> httpx.Response:
        seen.append((req.method, req.url.path))
        return httpx.Response(
            200, json={"object": "list", "data": [{"id": "qwen2.5:0.5b"}, {"id": "other:1b"}]}
        )

    ids = _gateway(httpx.MockTransport(handler)).list_models()

    assert ids == ["qwen2.5:0.5b", "other:1b"]
    assert seen == [("GET", "/v1/models")]


def test_list_models_empty_server_returns_empty_list() -> None:
    """spec 0006 R-9: 빈 볼륨의 서버는 `data: []` - 오류가 아니라 빈 목록이다(판정은 호출자)."""
    gateway = _gateway(httpx.MockTransport(lambda req: httpx.Response(200, json={"data": []})))

    assert gateway.list_models() == []


def test_list_models_http_error_is_model_error_http() -> None:
    """spec 0006 R-9: 5xx 는 `ModelError(kind="http")` - 조용히 빈 목록으로 만들지 않는다."""
    gateway = _gateway(httpx.MockTransport(lambda req: httpx.Response(503, text="loading")))

    with pytest.raises(ModelError) as exc_info:
        gateway.list_models()

    assert exc_info.value.kind == "http"
    assert exc_info.value.status == 503


def test_list_models_connection_failure_is_model_error_protocol() -> None:
    """spec 0006 R-9: 서버에 닿지 못하면 `ModelError(kind="protocol")`."""

    def handler(req: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("no route", request=req)

    with pytest.raises(ModelError) as exc_info:
        _gateway(httpx.MockTransport(handler)).list_models()

    assert exc_info.value.kind == "protocol"
