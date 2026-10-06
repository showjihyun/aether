"""spec 0004 R-1, R-2, D-6, D-7, D-12, C-2: `CompileContextUseCase` 의 계약 테스트.

컨테이너·네트워크 없음 — 순수 조립 로직만 검증합니다(AR-9).
"""

from __future__ import annotations

import math

from aether_context.adapters.outbound.token_counter.char_approx import CharApproxTokenCounter
from aether_context.application.ports.inbound.compile_context import CompileContextRequest
from aether_context.application.usecases.compile_context import CompileContextUseCase
from aether_context.domain.message import ContextMessage
from aether_context.domain.tool_schema import ContextToolSchema


def _counter() -> CharApproxTokenCounter:
    return CharApproxTokenCounter()


def _usecase() -> CompileContextUseCase:
    return CompileContextUseCase(_counter())


def test_char_approx_token_counter_rounds_up_overestimate_direction() -> None:
    """spec D-6, C-2: 문자 ÷ 4 를 올림 — 어긋남은 과대 추정 방향으로 고정됩니다.

    `count(text) * 4 >= len(text)` 가 항상 참이면(바닥 나눔이 아니라 올림), 추정이
    실제 글자 수를 절대 과소평가하지 않습니다 — 올림이 아니라 버림이었다면 나누어
    떨어지지 않는 길이에서 이 부등식이 깨집니다.
    """
    counter = _counter()
    for length in range(0, 40):
        text = "x" * length
        tokens = counter.count(text)
        assert tokens * 4 >= length
        assert tokens == math.ceil(length / 4)


def test_compile_is_deterministic_across_100_repeats() -> None:
    """spec R-1, D-12: 같은 입력 100회 조립이 전부 동일한 결과를 냅니다."""
    usecase = _usecase()
    request = CompileContextRequest(
        system_prompt="너는 도움이 되는 비서다.",
        budget_tokens=100,
        conversation=tuple(
            ContextMessage(role="user" if i % 2 == 0 else "assistant", content=f"turn {i}" * 5)
            for i in range(10)
        ),
        tools=(
            ContextToolSchema(name="search", description="검색한다" * 10, input_schema={"a": 1}),
            ContextToolSchema(name="calc", description="계산한다" * 10, input_schema={"b": 2}),
        ),
    )

    results = [usecase(request) for _ in range(100)]
    first = results[0]
    for other in results[1:]:
        assert other == first


def test_budget_overflow_drops_in_d7_order_and_keeps_system_and_latest_pair() -> None:
    """spec R-2, D-7: 예산의 3배 입력이 예산 이하로 줄고, 제거 기록이 D-7 순서
    (v1 에는 Memory·Knowledge 가 없으므로 실제로는 오래된 대화 → 도구 설명)를
    따릅니다. `system` 과 가장 최근 대화 한 쌍은 빼지 않습니다."""
    usecase = _usecase()

    system_prompt = "system prompt"
    conversation = tuple(
        ContextMessage(
            role="user" if i % 2 == 0 else "assistant", content=f"message number {i} " * 20
        )
        for i in range(12)
    )
    tools = (ContextToolSchema(name="t1", description="d" * 200, input_schema={}),)

    full_request = CompileContextRequest(
        system_prompt=system_prompt, budget_tokens=10_000, conversation=conversation, tools=tools
    )
    full_result = usecase(full_request)
    budget = full_result.report.total_tokens // 3

    request = CompileContextRequest(
        system_prompt=system_prompt, budget_tokens=budget, conversation=conversation, tools=tools
    )
    result = usecase(request)

    assert result.report.total_tokens <= budget
    assert result.report.budget_tokens == budget

    # system 은 항상 남습니다.
    assert result.messages[0].role == "system"
    assert result.messages[0].content == system_prompt

    # 가장 최근 대화 한 쌍(마지막 두 메시지)은 항상 남습니다.
    kept_tail = tuple(m.content for m in result.messages[-2:])
    assert kept_tail == (conversation[-2].content, conversation[-1].content)

    dropped_sources = [d.source for d in result.report.dropped]
    # D-7: 오래된 대화가 도구 설명보다 먼저(또는 단독으로) 빠집니다.
    if "tools" in dropped_sources and "conversation" in dropped_sources:
        assert dropped_sources.index("conversation") < dropped_sources.index("tools")
    assert "memory" not in dropped_sources
    assert "knowledge" not in dropped_sources


def test_no_drop_when_within_budget() -> None:
    """예산 안이면 아무것도 빼지 않고 전부 조립됩니다."""
    usecase = _usecase()
    request = CompileContextRequest(
        system_prompt="s",
        budget_tokens=10_000,
        conversation=(ContextMessage(role="user", content="hi"),),
        tools=(),
    )
    result = usecase(request)
    assert result.report.dropped == ()
    assert len(result.messages) == 2  # system + 1 conversation message
