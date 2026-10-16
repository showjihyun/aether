"""spec 0005 2.8 개정 9, R-14, AR-6 (P4-5): `ToolGatewayInvoker` - `aether_workflow` 의
`ToolInvoker` 포트를 runtime 의 `ToolGateway`(= MCP Gateway: 판정 -> 호출 -> 감사)로 구현합니다.

새 통로를 만들지 않습니다: Agent Run 의 도구 호출과 **같은 게이트웨이**(`_build_tool_gateway`)를
지나므로 기본 deny Policy 와 `data.tool_call_audit` 가 그대로 적용됩니다. 노드의 `tool_server` 는
서버 표의 키(`ref`)이자 정책·감사의 `server_name` 입니다(`bind` 가 둘을 같게 둡니다 - Agent 가
바인딩의 `name` 을 따로 고정하는 것과 달리 노드는 서버 이름 하나만 가집니다).

`gateway_factory` 는 `run_kind="workflow"` 인 게이트웨이를 만들어야 합니다(개정 10) - 감사 행이
Workflow Run 의 것으로 남습니다.

호출마다 **새 게이트웨이**를 만듭니다 - `bind` 는 게이트웨이의 가변 상태이고 `CallTool` 의 도구 목록
캐시도 인스턴스 수명입니다. 만드는 비용은 객체 몇 개뿐입니다(연결은 호출마다 새로 엽니다, spec 0003
2.2). 거부는 `ToolInvocationDenied`, 그 밖의 실패(없는 도구·호출 실패)는 `ToolInvocationFailed` 로
옮깁니다. `discover` 는 도구 이름 -> 서버 매핑을 채우려고 부릅니다(`call` 의 전제).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any
from uuid import UUID

from aether_runtime.application.ports.outbound.tool_gateway import (
    ToolCallDenied,
    ToolCallFailed,
    ToolGateway,
    ToolNotFound,
)
from aether_runtime.domain.agent import McpServerBinding
from aether_workflow.application.ports.outbound.tool_invoker import (
    ToolInvocationDenied,
    ToolInvocationFailed,
    ToolOutcome,
)


class ToolGatewayInvoker:
    """`aether_workflow.application.ports.outbound.tool_invoker.ToolInvoker` 의 구현."""

    def __init__(self, gateway_factory: Callable[[], ToolGateway]) -> None:
        self._gateway_factory = gateway_factory

    def call(
        self,
        workflow_run_id: UUID,
        agent_version_id: UUID,
        server: str,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> ToolOutcome:
        gateway = self._gateway_factory()
        try:
            gateway.bind((McpServerBinding(name=server, transport="stdio", ref=server),))
            gateway.discover()
            result = gateway.call(workflow_run_id, agent_version_id, tool_name, arguments)
        except ToolCallDenied as exc:
            raise ToolInvocationDenied(str(exc)) from exc
        except (ToolCallFailed, ToolNotFound) as exc:
            raise ToolInvocationFailed(str(exc)) from exc
        finally:
            gateway.close()
        return ToolOutcome(content=result.content, is_error=result.is_error)
