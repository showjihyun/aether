"""spec 0003 2.1, 2.5, 2.6, AR-6, AR-12, D-9, R-9 (P2-6): `McpToolGateway` — `ToolGateway`
(outbound) 의 유일한 구현. `aether_mcp` 의 **inbound 포트 타입만** 봅니다 — `CallTool`·
`DiscoverTools` 의 Protocol 타입과 `domain` 값 타입만 import 하고, `aether_mcp.
adapters`·`aether_mcp.application.usecases` 는 import 하지 않습니다(실제 구현
조립은 worker 의 `main.py` 가 맡습니다, AR-10).

**바인딩(P2-6).** 생성자는 `server_table`(worker 가 `AETHER_MCP_SERVERS` 를 풀어
만든 `binding.ref -> McpServerRef` 표, spec 2.9)을 받습니다 — 실제 명령·URL 자체는
알지 못하고 worker 가 이미 푼 값만 봅니다. `bind(mcp_servers)` 가 그 Run 의
`AgentDefinition.mcp_servers`(D-2)를 받아 `server_table` 로 각 `ref` 를 풀고,
표에 없는 `ref` 는 조용히 빠집니다(spec 2.9 — 배포 설정에 없는 서버는 그 Run 에서
빠지되 Run 은 계속합니다). 풀린 `McpServerRef` 의 `name` 은 바인딩의 `name` 으로
바꿔 씁니다 — 감사·정책의 신분은 `ref`(배포가 아는 이름)가 아니라 `name`(Agent
작성자가 고정한 이름, spec 2.7 개정 4)이어야 하기 때문입니다.

**Discovery 라우팅.** `discover()` 는 바인딩된 서버마다 `DiscoverTools` 를 불러
합칩니다. 한 서버가 예외를 올리면(연결 실패) 그 서버만 건너뛰고 나머지는 계속
합니다(spec 2.5) — 같은 이름이 여러 서버에 있으면 먼저 바인딩된 서버가 이깁니다.
그 매핑(`도구 이름 -> 서버`)을 `call()` 이 그대로 씁니다.

**호출 라우팅과 미지 도구의 감사 귀속(2026-09-28 수정, 코디네이터 지적).** `call()`
은 직전 `discover()` 가 만든 매핑으로 서버를 찾습니다. 매핑에 없는 이름은 **어느
바인딩된 서버로도 라우팅하지 않습니다** — 실제 서버로 라우팅하면 그 서버가 요청받은
적 없는 호출의 감사를 떠안는 거짓 귀속이 됩니다(감사는 규제·심사 대상 표면이므로
"누가 무엇을 불렀나" 가 틀리면 안 됩니다). 대신 `_UNBOUND_SENTINEL`(실제 서버
이름과 겹치지 않는 표지, `name="(unbound)"`)로 `CallTool`(aether_mcp) 을 불러
감사만 남깁니다(spec 2.5 "그 시도도 감사에 남습니다") — 바인딩된 서버가 전혀 없는
경우도 같은 경로입니다("바인딩이 비어 있으면 도구 없이 실행" 이지만 그 시도 자체는
여전히 감사됩니다). 이 표지는 정책 표(`control.tool_permissions`)에 행이 있을 수
없으므로(CLI 는 실제 바인딩된 이름으로만 allow 를 넣습니다) `CallTool` 의 판정은
기본값 deny 로 떨어지고(spec 2.4, D-6), 감사에는 `decision="deny"`·
`outcome="denied"` 가 남습니다 — "이 호출은 애초에 허가될 수 없었다" 는 뜻으로
정직합니다(판정을 요청한 적 없다는 뜻의 `allow` 를 남기지 않습니다). `aether_mcp`
가 무엇을 올리든(`ToolCallDenied`/`ToolCallFailed`/`ToolNotFound`) 이 표지 경로는
항상 runtime 의 `ToolNotFound` 로 번역합니다 — Executor 관점에서 이것은 '없는
도구' 이지 '거부된 도구' 가 아니기 때문입니다(`FailureReason.UNKNOWN_TOOL` 을
그대로 유지, `TOOL_DENIED` 로 바뀌면 안 됩니다).

예외 변환(spec 2.4, 2.5): `aether_mcp.domain.errors` 의 `ToolCallDenied`·
`ToolCallFailed`·`ToolNotFound` 를 이 패키지의 같은 이름 예외로 바꿔 다시 던집니다
— Executor 는 `aether_mcp` 를 몰라도 됩니다. 그 밖의 예외(변환 대상이 아닌 것)는
그대로 전파합니다.

`close()`: 지금 구현(`StdioMcpClient`/`HttpMcpClient`)은 호출마다 서버 프로세스를
새로 열고 닫으므로(spec 2.2, D-11) 정리할 지속 연결이 없습니다 — no-op 입니다.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any
from uuid import UUID

from aether_mcp.application.ports.inbound.call_tool import CallTool
from aether_mcp.application.ports.inbound.discover_tools import DiscoverTools
from aether_mcp.domain.errors import ToolCallDenied as McpToolCallDenied
from aether_mcp.domain.errors import ToolCallFailed as McpToolCallFailed
from aether_mcp.domain.errors import ToolNotFound as McpToolNotFound
from aether_mcp.domain.tools import McpServerRef
from aether_mcp.domain.tools import ToolCall as McpToolCall

from aether_runtime.application.ports.outbound.model_gateway import ToolSchema
from aether_runtime.application.ports.outbound.tool_gateway import (
    ToolCallDenied,
    ToolCallFailed,
    ToolNotFound,
)
from aether_runtime.domain.agent import McpServerBinding
from aether_runtime.domain.tools import ToolResult

_UNBOUND_SENTINEL = McpServerRef(name="(unbound)", transport="stdio", command="(unbound)")
"""spec 2.5 (2026-09-28 수정): 이름이 어느 바인딩된 서버에도 없을 때 감사 귀속에
쓰는 표지 — 실제 배포에서 쓰이는 서버 이름과 겹치지 않도록 `(`·`)` 를 포함합니다
(`AgentDefinition.mcp_servers[].name`·`AETHER_MCP_SERVERS` 의 키 어디에도 이
문자들을 쓸 이유가 없습니다). `CallTool` 에 실제로 전달되지만, 정책 표에는 이
이름에 대한 허용 행이 있을 수 없으므로 항상 기본값 deny 로 판정됩니다(연결을
실제로 시도하지 않습니다 — judge 가 client 호출보다 먼저입니다, spec 2.4)."""


def _rebind_name(ref: McpServerRef, name: str) -> McpServerRef:
    """`server_table` 이 푼 `McpServerRef`(배포가 아는 이름)를 바인딩의 `name`
    (Agent 작성자가 고정한 이름, 감사·정책의 신분)으로 다시 씁니다."""
    return McpServerRef(
        name=name,
        transport=ref.transport,
        command=ref.command,
        args=ref.args,
        env=ref.env,
        url=ref.url,
    )


class McpToolGateway:
    """`ToolGateway` 포트 구현 — `bind()` 된 서버 집합으로 `CallTool`·
    `DiscoverTools`(둘 다 `aether_mcp` inbound 포트)를 부릅니다."""

    def __init__(
        self,
        *,
        call_tool: CallTool,
        discover_tools: DiscoverTools,
        server_table: Mapping[str, McpServerRef],
    ) -> None:
        self._call_tool = call_tool
        self._discover_tools = discover_tools
        self._server_table = server_table
        self._bound_servers: tuple[McpServerRef, ...] = ()
        self._tool_server: dict[str, McpServerRef] = {}

    def bind(self, mcp_servers: tuple[McpServerBinding, ...]) -> None:
        resolved: list[McpServerRef] = []
        for binding in mcp_servers:
            entry = self._server_table.get(binding.ref)
            if entry is None:
                continue
            resolved.append(_rebind_name(entry, binding.name))
        self._bound_servers = tuple(resolved)
        self._tool_server = {}

    def discover(self) -> tuple[ToolSchema, ...]:
        merged: dict[str, ToolSchema] = {}
        tool_server: dict[str, McpServerRef] = {}
        for server in self._bound_servers:
            try:
                tools = self._discover_tools(server)
            except Exception:  # noqa: BLE001 - 연결 실패는 이 서버만 건너뜁니다
                continue
            for tool in tools:
                if tool.name in merged:
                    continue
                merged[tool.name] = ToolSchema(
                    name=tool.name, description=tool.description, input_schema=tool.input_schema
                )
                tool_server[tool.name] = server
        self._tool_server = tool_server
        return tuple(merged.values())

    def call(
        self, run_id: UUID, agent_version_id: UUID, name: str, arguments: dict[str, Any]
    ) -> ToolResult:
        server = self._tool_server.get(name)
        if server is None:
            # spec 2.5 (2026-09-28 수정): 실제 바인딩된 서버로 라우팅하지 않습니다
            # — 그 서버가 요청받은 적 없는 호출의 감사를 떠안는 거짓 귀속이 됩니다.
            # 표지로 `CallTool` 을 불러 감사만 남기고, aether_mcp 가 무엇을 올리든
            # 이 어댑터는 항상 `ToolNotFound` 로 번역합니다.
            self._call_unbound_for_audit_only(run_id, agent_version_id, name, arguments)
            raise ToolNotFound(name)

        call = McpToolCall(
            run_id=run_id,
            agent_version_id=agent_version_id,
            server=server,
            tool_name=name,
            arguments=arguments,
        )
        try:
            result = self._call_tool(call)
        except McpToolCallDenied as exc:
            raise ToolCallDenied(str(exc)) from exc
        except McpToolNotFound as exc:
            raise ToolNotFound(str(exc)) from exc
        except McpToolCallFailed as exc:
            raise ToolCallFailed(str(exc)) from exc
        return ToolResult(content=result.content, is_error=result.is_error)

    def _call_unbound_for_audit_only(
        self, run_id: UUID, agent_version_id: UUID, name: str, arguments: dict[str, Any]
    ) -> None:
        """`_UNBOUND_SENTINEL` 로 `CallTool` 을 불러 감사 1건을 남깁니다. 결과는
        쓰지 않습니다 — 호출자는 이 뒤에 항상 `ToolNotFound` 를 올립니다."""
        call = McpToolCall(
            run_id=run_id,
            agent_version_id=agent_version_id,
            server=_UNBOUND_SENTINEL,
            tool_name=name,
            arguments=arguments,
        )
        try:
            self._call_tool(call)
        except (McpToolCallDenied, McpToolNotFound, McpToolCallFailed):
            return
        # `CallTool` 이 예외 없이 성공을 돌려주는 것은(정책 표에 이 표지에 대한
        # allow 행이 실수로 들어간 경우 등) 이 경로가 전제하지 않는 상태입니다 —
        # 그래도 이 이름은 어느 실제 서버에도 없으므로 호출자는 그대로 `ToolNotFound`
        # 를 올립니다(위에서 처리, 여기서는 그냥 반환).

    def close(self) -> None:
        """spec 2.5: Run 종결마다 불립니다. 호출마다 여는/닫는 지금 구현에는
        정리할 지속 연결이 없으므로 no-op 입니다."""
        return None
