"""spec 0005 2.8 개정 9, R-14 (P4-5): `LLM`·`TOOL`·`MCP` 노드의 어댑터 - worker 의 조립 쪽.

`ModelGatewayInvoker` 는 `ModelGateway`(AR-5)를, `ToolGatewayInvoker` 는 runtime 의 `ToolGateway`
(= MCP Gateway, AR-6: 판정 -> 호출 -> 감사)를 **그대로** 지난다. 컨테이너 없이(fake 게이트웨이).

증명하는 것: 모델은 `user` 메시지 하나로 한 번 부르고 본문·종료 사유를 돌려준다 / 도구는
`bind -> discover -> call` 순서로 부르고 권한 주체(Version)와 감사의 `run_id` 를 그대로 넘긴다 /
Gateway 의 거부는 `ToolInvocationDenied`, 그 밖의 실패는 `ToolInvocationFailed` 로 옮긴다 /
매 호출이 새 게이트웨이를 만든다(바인딩 상태를 호출 사이에 새게 하지 않는다).
"""

from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

import pytest
from aether_runtime.adapters.outbound.model_gateway.fake import FakeModelGateway
from aether_runtime.application.ports.outbound.model_gateway import ModelError, ToolSchema
from aether_runtime.application.ports.outbound.tool_gateway import (
    ToolCallDenied,
    ToolCallFailed,
    ToolNotFound,
)
from aether_runtime.domain.agent import McpServerBinding
from aether_runtime.domain.tools import ToolResult
from aether_worker.adapters.outbound.model_invoker.model_gateway import ModelGatewayInvoker
from aether_worker.adapters.outbound.tool_invoker.tool_gateway import ToolGatewayInvoker
from aether_workflow.application.ports.outbound.tool_invoker import (
    ToolInvocationDenied,
    ToolInvocationFailed,
)


def test_model_invoker_sends_one_user_message_and_returns_text_and_finish_reason() -> None:
    """spec 0005 2.8 개정 9 (5), AR-5: 프롬프트가 `user` 메시지 하나로 게이트웨이를 지난다."""
    gateway = FakeModelGateway.echo()

    answer = ModelGatewayInvoker(gateway).invoke("hello there", None)

    assert (answer.text, answer.finish_reason) == ("hello there", "stop")
    (request,) = gateway.calls
    assert [(m.role, m.content) for m in request.messages] == [("user", "hello there")]
    assert request.model_id is None
    assert request.tools == []


def test_model_invoker_passes_the_model_id_through() -> None:
    """spec 0005 2.8: 모델 ID 를 지정하면 그대로 넘긴다(없으면 배포 기본)."""
    gateway = FakeModelGateway.echo()

    ModelGatewayInvoker(gateway).invoke("x", "some-model")

    assert gateway.calls[0].model_id == "some-model"


def test_model_invoker_lets_gateway_errors_propagate() -> None:
    """R-14: 실패를 삼키지 않는다 - 실행기가 `model_call_failed` 로 노드를 실패시킨다."""
    gateway = FakeModelGateway([ModelError("timeout")])

    with pytest.raises(ModelError):
        ModelGatewayInvoker(gateway).invoke("x", None)


class _RecordingToolGateway:
    """`ToolGateway` 를 만족하는 기록용 대역 - 부른 순서와 인자를 모은다."""

    def __init__(
        self, *, result: ToolResult | None = None, raises: Exception | None = None
    ) -> None:
        self.log: list[str] = []
        self.bound: tuple[McpServerBinding, ...] = ()
        self.call_args: tuple[UUID, UUID, str, dict[str, Any]] | None = None
        self._result = result or ToolResult(content="4")
        self._raises = raises

    def bind(self, mcp_servers: tuple[McpServerBinding, ...]) -> None:
        self.log.append("bind")
        self.bound = mcp_servers

    def discover(self) -> tuple[ToolSchema, ...]:
        self.log.append("discover")
        return ()

    def call(
        self,
        run_id: UUID,
        agent_version_id: UUID,
        name: str,
        arguments: dict[str, Any],
    ) -> ToolResult:
        self.log.append("call")
        self.call_args = (run_id, agent_version_id, name, arguments)
        if self._raises is not None:
            raise self._raises
        return self._result

    def close(self) -> None:
        self.log.append("close")


def test_tool_invoker_binds_discovers_calls_in_that_order_with_the_principal() -> None:
    """spec 0005 2.8 개정 9 (1), AR-6: `bind -> discover -> call -> close`, 주체·`run_id` 전달."""
    gateway = _RecordingToolGateway(result=ToolResult(content="4", is_error=False))
    run_id, version_id = uuid4(), uuid4()

    outcome = ToolGatewayInvoker(lambda: gateway).call(
        run_id, version_id, "builtin", "calculator", {"expression": "2+2"}
    )

    assert (outcome.content, outcome.is_error) == ("4", False)
    assert gateway.log == ["bind", "discover", "call", "close"]
    assert [(b.name, b.ref) for b in gateway.bound] == [("builtin", "builtin")]
    assert gateway.call_args == (run_id, version_id, "calculator", {"expression": "2+2"})


def test_tool_invoker_carries_is_error_through() -> None:
    """spec 0005 2.8 개정 9 (5): `is_error` 를 그대로 돌려준다(실패 판정은 실행기의 일)."""
    gateway = _RecordingToolGateway(result=ToolResult(content="boom", is_error=True))

    outcome = ToolGatewayInvoker(lambda: gateway).call(uuid4(), uuid4(), "s", "t", {})

    assert outcome.is_error is True


def test_tool_invoker_translates_a_denial() -> None:
    """spec 0005 2.8 개정 9 (1): Gateway 의 거부는 포트의 거부 예외로 - 구별되는 사유의 근거."""
    gateway = _RecordingToolGateway(raises=ToolCallDenied("builtin/calculator"))

    with pytest.raises(ToolInvocationDenied):
        ToolGatewayInvoker(lambda: gateway).call(uuid4(), uuid4(), "builtin", "calculator", {})
    assert gateway.log[-1] == "close"


@pytest.mark.parametrize("error", [ToolCallFailed("x"), ToolNotFound("x")])
def test_tool_invoker_translates_other_gateway_failures(error: Exception) -> None:
    """R-14: 없는 도구·호출 실패는 하나의 실패 예외로."""
    gateway = _RecordingToolGateway(raises=error)

    with pytest.raises(ToolInvocationFailed):
        ToolGatewayInvoker(lambda: gateway).call(uuid4(), uuid4(), "builtin", "calculator", {})


def test_tool_invoker_builds_a_fresh_gateway_per_call() -> None:
    """바인딩은 게이트웨이의 가변 상태다 - 호출 사이에 새지 않도록 매번 새로 만든다."""
    built: list[_RecordingToolGateway] = []

    def factory() -> _RecordingToolGateway:
        built.append(_RecordingToolGateway())
        return built[-1]

    invoker = ToolGatewayInvoker(factory)
    invoker.call(uuid4(), uuid4(), "a", "t", {})
    invoker.call(uuid4(), uuid4(), "b", "t", {})

    assert len(built) == 2
    assert [b.bound[0].name for b in built] == ["a", "b"]
