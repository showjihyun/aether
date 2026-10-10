"""spec 0004 2.2, 2.3, 2.5, D-5, D-6, D-7, D-8, D-11, D-12, R-1, R-2, R-8, R-9:
`CompileContextUseCase` — Context Compiler v1(`CompileContext` 의 유일한 구현).

다섯 소스 `system`·`conversation`·`tools`·`knowledge`(P3-3)·`memory`(P3-4)를 조립합니다.

**결정성(R-1, D-12).** 입력은 전부 `tuple`/`list` 로 들어오고, 이 유스케이스는
어떤 지점에서도 `set`·정렬되지 않은 `dict` 순회를 쓰지 않습니다 — 소스 순서는
항상 호출자가 건넨 순서(Knowledge·Memory 는 각 포트가 돌려준 순서) 그대로입니다.

**예산(R-2, D-7).** 먼저 전부를 담고 토큰을 추정한 뒤, 예산을 넘으면 D-7 의
순서로 뺍니다 — (0) Memory(score 가 큰 것부터, 전부) → (1) 오래된 대화(마지막 두
개는 보호) → (2) Knowledge 하위 순위(score 가 큰 것부터, 가장 먼 것이 먼저
빠짐) → (3) 도구 스키마의 `description`(이름·입력 스키마는 유지) 순서입니다.
`system` 은 항상 남습니다. Memory 는 검증 전 경험이라 가장 먼저 포기합니다(C-5).

**Knowledge(2.5, D-8, R-8, R-9).** 질의는 `conversation` 의 마지막
`role == "user"` 메시지입니다 — 없으면 검색하지 않습니다. `knowledge_sets` 가
비어 있어도 검색하지 않습니다. 검색 결과는 `render_knowledge_block` 로 표지를
단 뒤 **독립된 메시지 하나**(`role="user"`)로, system 다음·conversation 앞에
들어갑니다 — system 메시지에 섞지 않습니다(R-8). 출처(`source_path`)가 없는
결과는 넣지 않습니다.

**Memory(2.6, D-8, R-10).** `agent_id` 가 있고 `MemoryReader` 가 꽂혀 있을 때만, 같은
질의(마지막 user 메시지)로 읽습니다. `render_memory_block`(`verified=false`)으로
표지를 달고 Knowledge 와 **별도의 독립 메시지**로 넣습니다 — 합치지 않습니다.
"""

from __future__ import annotations

import json
from dataclasses import replace

from aether_context.application.ports.inbound.compile_context import (
    CompileContextRequest,
    CompileContextResult,
)
from aether_context.application.ports.outbound.knowledge_search import KnowledgeSearch
from aether_context.application.ports.outbound.memory_reader import MemoryReader
from aether_context.application.ports.outbound.token_counter import TokenCounter
from aether_context.domain.knowledge import SearchResult, render_knowledge_block
from aether_context.domain.memory import MemoryHit, render_memory_block
from aether_context.domain.message import ContextMessage
from aether_context.domain.report import ContextReport, DroppedSource, SourceTokens
from aether_context.domain.tool_schema import ContextToolSchema

_PROTECTED_CONVERSATION_TAIL = 2
"""spec D-7: "system 과 가장 최근 대화 한 쌍은 빼지 않습니다" — 대화의 마지막
이 개수만큼은 예산이 아무리 모자라도 빼지 않습니다."""


def _last_user_message(conversation: tuple[ContextMessage, ...]) -> str | None:
    """`conversation` 을 뒤에서부터 봐서 처음 만나는 `role == "user"` 의 내용.
    없으면 `None`(검색하지 않음, spec 2.5)."""
    for message in reversed(conversation):
        if message.role == "user":
            return message.content
    return None


class CompileContextUseCase:
    """`CompileContext`(inbound) 의 구현."""

    def __init__(
        self,
        token_counter: TokenCounter,
        knowledge_search: KnowledgeSearch | None = None,
        memory_reader: MemoryReader | None = None,
    ) -> None:
        self._memory_reader = memory_reader
        self._token_counter = token_counter
        self._knowledge_search = knowledge_search

    def __call__(self, request: CompileContextRequest) -> CompileContextResult:
        system_tokens = (
            self._token_counter.count(request.system_prompt) if request.system_prompt else 0
        )
        conversation_costs = [self._token_counter.count(m.content) for m in request.conversation]
        tool_costs = [self._tool_tokens(tool) for tool in request.tools]
        knowledge_results = self._search_knowledge(request)
        knowledge_blocks = [render_knowledge_block(result) for result in knowledge_results]
        knowledge_costs = [self._token_counter.count(block) for block in knowledge_blocks]
        memory_blocks = [render_memory_block(hit) for hit in self._read_memory(request)]
        memory_costs = [self._token_counter.count(block) for block in memory_blocks]

        source_tokens_list = [
            SourceTokens(source="system", tokens=system_tokens),
            SourceTokens(source="conversation", tokens=sum(conversation_costs)),
        ]
        if knowledge_blocks:
            source_tokens_list.append(SourceTokens(source="knowledge", tokens=sum(knowledge_costs)))
        if memory_blocks:
            source_tokens_list.append(SourceTokens(source="memory", tokens=sum(memory_costs)))
        source_tokens_list.append(SourceTokens(source="tools", tokens=sum(tool_costs)))
        source_tokens = tuple(source_tokens_list)

        kept_conversation = list(request.conversation)
        kept_conversation_costs = list(conversation_costs)
        kept_knowledge_blocks = list(knowledge_blocks)
        kept_knowledge_costs = list(knowledge_costs)
        kept_memory_blocks = list(memory_blocks)
        kept_memory_costs = list(memory_costs)
        kept_tools = list(request.tools)
        kept_tool_costs = list(tool_costs)

        total = (
            system_tokens
            + sum(kept_conversation_costs)
            + sum(kept_knowledge_costs)
            + sum(kept_memory_costs)
            + sum(kept_tool_costs)
        )
        dropped_memory_tokens = 0
        dropped_conversation_tokens = 0
        dropped_knowledge_tokens = 0
        dropped_tools_tokens = 0

        # D-7 (0): Memory 가 가장 먼저 빠집니다 — 검증 전 경험이므로 사실(Knowledge)이나
        # 대화보다 먼저 포기합니다. 하위 순위(목록의 맨 끝)부터 뺍니다.
        while total > request.budget_tokens and kept_memory_blocks:
            removed_cost = kept_memory_costs.pop()
            kept_memory_blocks.pop()
            dropped_memory_tokens += removed_cost
            total -= removed_cost

        protected = min(_PROTECTED_CONVERSATION_TAIL, len(kept_conversation))
        # D-7 (1): 오래된 대화부터 뺍니다. 가장 오래된 것은 목록의 맨 앞입니다 —
        # 보호된 마지막 `protected` 개는 건드리지 않습니다.
        while total > request.budget_tokens and len(kept_conversation) > protected:
            removed_cost = kept_conversation_costs.pop(0)
            kept_conversation.pop(0)
            dropped_conversation_tokens += removed_cost
            total -= removed_cost

        # D-7 (2): 그 다음 Knowledge 를 하위 순위(목록의 맨 끝, score 가 가장
        # 큰 것)부터 뺍니다 — `knowledge_results` 는 `KnowledgeSearch` 가 이미
        # score 오름차순(가까운 것 먼저)으로 돌려줍니다.
        while total > request.budget_tokens and kept_knowledge_blocks:
            removed_cost = kept_knowledge_costs.pop()
            kept_knowledge_blocks.pop()
            dropped_knowledge_tokens += removed_cost
            total -= removed_cost

        # D-7 (3): 그 다음 도구 스키마의 설명을 뺍니다(이름·입력 스키마는 유지) —
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
        if kept_knowledge_blocks:
            messages.append(ContextMessage(role="user", content="".join(kept_knowledge_blocks)))
        if kept_memory_blocks:
            messages.append(ContextMessage(role="user", content="".join(kept_memory_blocks)))
        messages.extend(kept_conversation)

        dropped: list[DroppedSource] = []
        if dropped_memory_tokens:
            dropped.append(DroppedSource(source="memory", tokens=dropped_memory_tokens))
        if dropped_conversation_tokens:
            dropped.append(DroppedSource(source="conversation", tokens=dropped_conversation_tokens))
        if dropped_knowledge_tokens:
            dropped.append(DroppedSource(source="knowledge", tokens=dropped_knowledge_tokens))
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

    def _search_knowledge(self, request: CompileContextRequest) -> tuple[SearchResult, ...]:
        if not request.knowledge_sets or self._knowledge_search is None:
            return ()
        query = _last_user_message(request.conversation)
        if query is None:
            return ()
        results = self._knowledge_search.search(
            request.knowledge_sets, query, top_k=request.knowledge_top_k
        )
        # spec 2.5: 출처 없는 결과는 넣지 않습니다 — 출처 없는 사실은 검증할 수
        # 없습니다.
        return tuple(result for result in results if result.source_path)

    def _read_memory(self, request: CompileContextRequest) -> tuple[MemoryHit, ...]:
        if request.agent_id is None or self._memory_reader is None:
            return ()
        query = _last_user_message(request.conversation)
        if query is None:
            return ()
        return self._memory_reader.read(request.agent_id, query, top_k=request.memory_top_k)

    def _tool_tokens(self, tool: ContextToolSchema) -> int:
        text = tool.name + tool.description + json.dumps(tool.input_schema, sort_keys=True)
        return self._token_counter.count(text)
