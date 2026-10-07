"""spec 0004 2.2, 2.3, D-6, D-7, D-11, D-12, R-1, R-2: `CompileContextUseCase` —
Context Compiler v1(`CompileContext` 의 유일한 구현).

v1 은 `system`·`conversation`·`tools` 세 소스만 조립합니다 — `knowledge`·`memory`
포트는 이 단위(P3-1)에 선언하지 않습니다(P3-3·P3-4 의 범위).

**결정성(R-1, D-12).** 입력은 전부 `tuple`/`list` 로 들어오고, 이 유스케이스는
어떤 지점에서도 `set`·정렬되지 않은 `dict` 순회를 쓰지 않습니다 — 소스 순서는
항상 호출자가 건넨 순서 그대로입니다.

**예산(R-2, D-7).** 먼저 전부를 담고 토큰을 추정한 뒤, 예산을 넘으면 D-7 의
순서로 뺍니다 — v1 에는 Memory·Knowledge 가 없으므로 실제로는 (1) 오래된 대화
(마지막 두 개는 보호) → (2) 도구 스키마의 `description`(이름·입력 스키마는 유지)
순서입니다. `system` 은 항상 남습니다.
"""

from __future__ import annotations

import json
from dataclasses import replace

from aether_context.application.ports.inbound.compile_context import (
    CompileContextRequest,
    CompileContextResult,
)
from aether_context.application.ports.outbound.token_counter import TokenCounter
from aether_context.domain.message import ContextMessage
from aether_context.domain.report import ContextReport, DroppedSource, SourceTokens
from aether_context.domain.tool_schema import ContextToolSchema

_PROTECTED_CONVERSATION_TAIL = 2
"""spec D-7: "system 과 가장 최근 대화 한 쌍은 빼지 않습니다" — 대화의 마지막
이 개수만큼은 예산이 아무리 모자라도 빼지 않습니다."""


class CompileContextUseCase:
    """`CompileContext`(inbound) 의 구현."""

    def __init__(self, token_counter: TokenCounter) -> None:
        self._token_counter = token_counter

    def __call__(self, request: CompileContextRequest) -> CompileContextResult:
        system_tokens = (
            self._token_counter.count(request.system_prompt) if request.system_prompt else 0
        )
        conversation_costs = [self._token_counter.count(m.content) for m in request.conversation]
        tool_costs = [self._tool_tokens(tool) for tool in request.tools]

        source_tokens = (
            SourceTokens(source="system", tokens=system_tokens),
            SourceTokens(source="conversation", tokens=sum(conversation_costs)),
            SourceTokens(source="tools", tokens=sum(tool_costs)),
        )

        kept_conversation = list(request.conversation)
        kept_conversation_costs = list(conversation_costs)
        kept_tools = list(request.tools)
        kept_tool_costs = list(tool_costs)

        total = system_tokens + sum(kept_conversation_costs) + sum(kept_tool_costs)
        dropped_conversation_tokens = 0
        dropped_tools_tokens = 0

        protected = min(_PROTECTED_CONVERSATION_TAIL, len(kept_conversation))
        # D-7 (1): 오래된 대화부터 뺍니다. 가장 오래된 것은 목록의 맨 앞입니다 —
        # 보호된 마지막 `protected` 개는 건드리지 않습니다.
        while total > request.budget_tokens and len(kept_conversation) > protected:
            removed_cost = kept_conversation_costs.pop(0)
            kept_conversation.pop(0)
            dropped_conversation_tokens += removed_cost
            total -= removed_cost

        # D-7 (2): 그 다음 도구 스키마의 설명을 뺍니다(이름·입력 스키마는 유지) —
        # 주어진 순서대로, 설명이 있는 도구만 대상입니다.
        if total > request.budget_tokens:
            for index, tool in enumerate(kept_tools):
                if total <= request.budget_tokens:
                    break
                if not tool.description:
                    continue
                trimmed = replace(tool, description="")
                removed_cost = kept_tool_costs[index] - self._tool_tokens(trimmed)
                kept_tools[index] = trimmed
                kept_tool_costs[index] = self._tool_tokens(trimmed)
                dropped_tools_tokens += removed_cost
                total -= removed_cost

        messages: list[ContextMessage] = []
        if request.system_prompt:
            messages.append(ContextMessage(role="system", content=request.system_prompt))
        messages.extend(kept_conversation)

        dropped: list[DroppedSource] = []
        if dropped_conversation_tokens:
            dropped.append(DroppedSource(source="conversation", tokens=dropped_conversation_tokens))
        if dropped_tools_tokens:
            dropped.append(DroppedSource(source="tools", tokens=dropped_tools_tokens))

        report = ContextReport(
            budget_tokens=request.budget_tokens,
            source_tokens=source_tokens,
            total_tokens=total,
            dropped=tuple(dropped),
        )
        return CompileContextResult(
            messages=tuple(messages), tools=tuple(kept_tools), report=report
        )

    def _tool_tokens(self, tool: ContextToolSchema) -> int:
        text = tool.name + tool.description + json.dumps(tool.input_schema, sort_keys=True)
        return self._token_counter.count(text)
