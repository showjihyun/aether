"""spec 0004 2.1, AR-3, AR-12, D-11, R-3 (P3-1): `AetherContextCompiler` —
`ContextCompiler`(outbound) 의 유일한 구현.

`aether_context` 의 **inbound 포트 타입만** 봅니다(`CompileContext`, `domain` 의
값 타입) — `aether_context.adapters`·`aether_context.application.usecases` 는
import 하지 않습니다(실제 구현 조립은 worker 의 `main.py` 가 맡습니다, AR-10).
`McpToolGateway`(spec 0003)와 같은 자리입니다.

변환만 합니다: runtime 쪽 `Message`/`ToolSchema` ↔ `aether_context` 쪽
`ContextMessage`/`ContextToolSchema`, 그리고 `aether_context.domain.report.
ContextReport` → 이 패키지의 `ContextReport`(outbound 포트의 값 타입).
"""

from __future__ import annotations

from uuid import UUID

from aether_context.application.ports.inbound.compile_context import (
    CompileContext,
    CompileContextRequest,
)
from aether_context.domain.message import ContextMessage as AetherContextMessage
from aether_context.domain.report import ContextReport as AetherContextReport
from aether_context.domain.tool_schema import ContextToolSchema

from aether_runtime.application.ports.outbound.context_compiler import (
    DEFAULT_KNOWLEDGE_TOP_K,
    CompiledContext,
    ContextDrop,
    ContextReport,
    ContextSourceTokens,
)
from aether_runtime.application.ports.outbound.model_gateway import ToolSchema
from aether_runtime.domain.run import Message


def _to_context_message(message: Message) -> AetherContextMessage:
    return AetherContextMessage(
        role=message.role, content=message.content, tool_call_id=message.tool_call_id
    )


def _from_context_message(message: AetherContextMessage) -> Message:
    return Message(role=message.role, content=message.content, tool_call_id=message.tool_call_id)


def _to_context_tool(tool: ToolSchema) -> ContextToolSchema:
    return ContextToolSchema(
        name=tool.name, description=tool.description, input_schema=tool.input_schema
    )


def _from_context_tool(tool: ContextToolSchema) -> ToolSchema:
    return ToolSchema(name=tool.name, description=tool.description, input_schema=tool.input_schema)


def _translate_report(report: AetherContextReport) -> ContextReport:
    return ContextReport(
        budget_tokens=report.budget_tokens,
        source_tokens=tuple(
            ContextSourceTokens(source=item.source, tokens=item.tokens)
            for item in report.source_tokens
        ),
        total_tokens=report.total_tokens,
        dropped=tuple(
            ContextDrop(source=item.source, tokens=item.tokens) for item in report.dropped
        ),
    )


class AetherContextCompiler:
    """`ContextCompiler` 포트 구현 — 주입된 `compile_context`(`aether_context`
    의 `CompileContext` inbound 포트 구현)를 부릅니다."""

    def __init__(self, compile_context: CompileContext) -> None:
        self._compile_context = compile_context

    def compile(
        self,
        *,
        system_prompt: str,
        conversation: tuple[Message, ...],
        tools: tuple[ToolSchema, ...],
        budget_tokens: int,
        knowledge_sets: tuple[str, ...] = (),
        knowledge_top_k: int = DEFAULT_KNOWLEDGE_TOP_K,
        agent_id: UUID | None = None,
    ) -> CompiledContext:
        request = CompileContextRequest(
            system_prompt=system_prompt,
            budget_tokens=budget_tokens,
            conversation=tuple(_to_context_message(m) for m in conversation),
            tools=tuple(_to_context_tool(t) for t in tools),
            knowledge_sets=knowledge_sets,
            knowledge_top_k=knowledge_top_k,
            agent_id=agent_id,
        )
        result = self._compile_context(request)
        return CompiledContext(
            messages=tuple(_from_context_message(m) for m in result.messages),
            tools=tuple(_from_context_tool(t) for t in result.tools),
            report=_translate_report(result.report),
        )
