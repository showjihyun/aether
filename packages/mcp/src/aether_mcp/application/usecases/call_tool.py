"""spec 0003 2.4, D-9, D-10, D-11, 2.5, D-16: `CallToolUseCase` — `CallTool`(inbound)
의 유일한 구현. **진입점은 이것 하나입니다** — 테스트용 우회 함수를 만들지 않습니다.

고정 순서(D-9): 판정(호출마다, D-6, 캐시 없음) → deny 면 클라이언트를 부르지 않고
감사 뒤 `ToolCallDenied` → allow 면 도구 존재 확인(연결 수명, spec 2.5)과 호출 →
성공·실패·거부 세 경우 모두 감사 1건(D-9). 감사 실패는 호출 결과를 바꾸지
않습니다 — 로그에만 남깁니다(D-10).

연결 수명(spec 2.5): 이 유스케이스 인스턴스 하나가 Run 수명 하나에 대응합니다
(바인딩·재사용은 P2-3·P2-6). 서버별 도구 목록을 처음 쓸 때 한 번 `McpClient.discover`
로 얻어 인스턴스 안에 캐시합니다 — 그 서버가 실패하면 `None` 으로 캐시해 그 서버의
도구만 이후 호출에서 전부 `ToolNotFound` 로 빠지고(그 서버만, 다른 서버는 영향 없음),
Run(이 인스턴스)은 계속됩니다. 재연결은 discover 든 call 이든 **호출 1회 안에서
최대 1번**만 재시도합니다(D-11) — 무한 재시도를 넣지 않습니다.

타임아웃 강제는 이 유스케이스의 책임이 아닙니다(spec 2.9) — `McpClient` 구현
(`adapters/outbound/mcp_client/{stdio,http}.py`)이 `AETHER_MCP_CALL_TIMEOUT_MS` 를
실제로 강제하고 초과 시 예외를 올립니다. 이 유스케이스는 그 예외를 다른 호출
실패와 같은 방식으로 `ToolCallFailed` 로 감싸고 감사의 `error_kind` 에 예외 종류를
남깁니다 — 시계 델타로 사후 판정하지 않습니다.

`aether_mcp` 는 `aether_policy` 의 **inbound 포트 타입만** 봅니다(AR-4 방향,
spec 2.1) — `aether_policy.adapters` 를 import 하지 않습니다.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import UTC, datetime
from typing import TypeVar

from aether_policy.application.ports.inbound.judge_tool_call import JudgeToolCall

from aether_mcp.application.ports.outbound.audit_sink import AuditSink
from aether_mcp.application.ports.outbound.mcp_client import McpClient
from aether_mcp.domain.audit import AuditRecord, Decision, Outcome
from aether_mcp.domain.errors import ToolCallDenied, ToolCallFailed, ToolNotFound
from aether_mcp.domain.tools import McpServerRef, Tool, ToolCall, ToolResult

logger = logging.getLogger(__name__)

_T = TypeVar("_T")

_DEFAULT_MAX_RESULT_BYTES = 262_144


def _default_clock() -> datetime:
    return datetime.now(UTC)


class CallToolUseCase:
    def __init__(
        self,
        judge: JudgeToolCall,
        client: McpClient,
        audit: AuditSink,
        *,
        clock: Callable[[], datetime] = _default_clock,
        max_result_bytes: int = _DEFAULT_MAX_RESULT_BYTES,
    ) -> None:
        self._judge = judge
        self._client = client
        self._audit = audit
        self._clock = clock
        self._max_result_bytes = max_result_bytes
        self._known_tools: dict[str, tuple[Tool, ...] | None] = {}

    def __call__(self, call: ToolCall) -> ToolResult:
        started_at = self._clock()

        decision = self._judge(
            agent_version_id=call.agent_version_id,
            server_name=call.server.name,
            tool_name=call.tool_name,
        )
        if decision == "deny":
            self._safe_audit(
                self._record(
                    call,
                    started_at,
                    decision="deny",
                    outcome="denied",
                    result_bytes=0,
                    error_kind=None,
                )
            )
            raise ToolCallDenied(f"{call.server.name}/{call.tool_name} denied")

        tools = self._resolve_tools(call.server)
        if tools is None or call.tool_name not in {tool.name for tool in tools}:
            self._safe_audit(
                self._record(
                    call,
                    started_at,
                    decision="allow",
                    outcome="error",
                    result_bytes=0,
                    error_kind="tool_not_found",
                )
            )
            raise ToolNotFound(f"{call.server.name}/{call.tool_name}")

        try:
            result = self._reconnect_once(
                lambda: self._client.call(call.server, call.tool_name, call.arguments)
            )
        except Exception as exc:
            self._safe_audit(
                self._record(
                    call,
                    started_at,
                    decision="allow",
                    outcome="error",
                    result_bytes=0,
                    error_kind=type(exc).__name__,
                )
            )
            raise ToolCallFailed(f"{call.server.name}/{call.tool_name} failed") from exc

        original_bytes = len(result.content.encode("utf-8"))
        content = result.content
        if original_bytes > self._max_result_bytes:
            content = content.encode("utf-8")[: self._max_result_bytes].decode(
                "utf-8", errors="ignore"
            )
        outcome: Outcome = "error" if result.is_error else "ok"
        self._safe_audit(
            self._record(
                call,
                started_at,
                decision="allow",
                outcome=outcome,
                result_bytes=original_bytes,
                error_kind="tool_error" if result.is_error else None,
            )
        )
        return ToolResult(content=content, is_error=result.is_error)

    def _resolve_tools(self, server: McpServerRef) -> tuple[Tool, ...] | None:
        if server.name in self._known_tools:
            return self._known_tools[server.name]
        try:
            tools = self._reconnect_once(lambda: self._client.discover(server))
        except Exception:
            tools = None
        self._known_tools[server.name] = tools
        return tools

    def _reconnect_once(self, fn: Callable[[], _T]) -> _T:
        """spec 2.5, D-11: 재연결은 호출 1회 안에서 최대 1번(무한 재시도 없음)."""
        try:
            return fn()
        except Exception:
            return fn()

    def _record(
        self,
        call: ToolCall,
        started_at: datetime,
        *,
        decision: Decision,
        outcome: Outcome,
        result_bytes: int,
        error_kind: str | None,
    ) -> AuditRecord:
        duration_ms = int((self._clock() - started_at).total_seconds() * 1000)
        return AuditRecord(
            run_id=call.run_id,
            agent_version_id=call.agent_version_id,
            server_name=call.server.name,
            tool_name=call.tool_name,
            decision=decision,
            outcome=outcome,
            result_bytes=result_bytes,
            error_kind=error_kind,
            started_at=started_at,
            duration_ms=duration_ms,
        )

    def _safe_audit(self, record: AuditRecord) -> None:
        """D-10: 감사 기록 실패는 호출 결과를 바꾸지 않습니다 — 로그에만 남깁니다."""
        try:
            self._audit.record(record)
        except Exception:
            logger.exception("audit sink failed to record %s", record)
