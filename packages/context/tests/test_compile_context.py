"""spec 0004 R-1, R-2, D-6, D-7, D-12, C-2: `CompileContextUseCase` 의 계약 테스트.

컨테이너·네트워크 없음 — 순수 조립 로직만 검증합니다(AR-9).
"""

from __future__ import annotations

import math

from aether_context.adapters.outbound.token_counter.char_approx import CharApproxTokenCounter
from aether_context.application.ports.inbound.compile_context import CompileContextRequest
from aether_context.application.usecases.compile_context import CompileContextUseCase
from aether_context.domain.knowledge import SearchResult
from aether_context.domain.message import ContextMessage
from aether_context.domain.tool_schema import ContextToolSchema


class FakeKnowledgeSearch:
    """`KnowledgeSearch`(outbound) 포트의 결정적 fake — 호출을 기록하고 미리
    준비된 결과를 그대로 돌려줍니다(네트워크·DB 없음, AR-9)."""

    def __init__(self, results: tuple[SearchResult, ...] = ()) -> None:
        self.results = results
        self.calls: list[tuple[tuple[str, ...], str, int]] = []

    def search(
        self, set_names: tuple[str, ...], query: str, *, top_k: int
    ) -> tuple[SearchResult, ...]:
        self.calls.append((set_names, query, top_k))
        return self.results


def _counter() -> CharApproxTokenCounter:
    return CharApproxTokenCounter()


def _usecase(knowledge_search: FakeKnowledgeSearch | None = None) -> CompileContextUseCase:
    return CompileContextUseCase(_counter(), knowledge_search)


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


def test_knowledge_query_is_the_last_user_message_in_conversation() -> None:
    """spec 2.5, D-5, D-8 (P3-3): 검색 질의는 `conversation` 의 **마지막
    `role == "user"` 메시지**입니다 — 그 뒤에 assistant 메시지가 있어도 가장
    최근 user 발화가 질의입니다."""
    search = FakeKnowledgeSearch()
    usecase = _usecase(search)
    request = CompileContextRequest(
        system_prompt="s",
        budget_tokens=10_000,
        conversation=(
            ContextMessage(role="user", content="first question"),
            ContextMessage(role="assistant", content="first answer"),
            ContextMessage(role="user", content="second question"),
        ),
        knowledge_sets=("docs",),
    )
    usecase(request)

    assert len(search.calls) == 1
    set_names, query, top_k = search.calls[0]
    assert set_names == ("docs",)
    assert query == "second question"
    assert top_k == request.knowledge_top_k


def test_knowledge_not_searched_without_user_message_in_conversation() -> None:
    """spec 2.5 (P3-3): user 메시지가 없으면 검색하지 않습니다 — 포트를 부르지
    않습니다."""
    search = FakeKnowledgeSearch()
    usecase = _usecase(search)
    request = CompileContextRequest(
        system_prompt="s",
        budget_tokens=10_000,
        conversation=(ContextMessage(role="assistant", content="hello"),),
        knowledge_sets=("docs",),
    )
    usecase(request)

    assert search.calls == []


def test_knowledge_not_searched_when_no_sets_bound() -> None:
    """`knowledge_sets` 가 빈 튜플(기본값)이면 포트를 부르지 않습니다."""
    search = FakeKnowledgeSearch()
    usecase = _usecase(search)
    request = CompileContextRequest(
        system_prompt="s",
        budget_tokens=10_000,
        conversation=(ContextMessage(role="user", content="q"),),
    )
    usecase(request)

    assert search.calls == []


def test_knowledge_results_without_source_path_are_excluded() -> None:
    """spec 2.5: "출처가 없는 청크는 넣지 않습니다" — `source_path` 가 빈 결과는
    Context 에 들어가지 않습니다."""
    search = FakeKnowledgeSearch(
        (
            SearchResult(source_path="", chunk_index=0, content="no source", score=0.1),
            SearchResult(source_path="doc.txt", chunk_index=0, content="has source", score=0.2),
        )
    )
    usecase = _usecase(search)
    request = CompileContextRequest(
        system_prompt="s",
        budget_tokens=10_000,
        conversation=(ContextMessage(role="user", content="q"),),
        knowledge_sets=("docs",),
    )
    result = usecase(request)

    knowledge_messages = [m for m in result.messages if "[knowledge " in m.content]
    assert len(knowledge_messages) == 1
    assert "has source" in knowledge_messages[0].content
    assert "no source" not in knowledge_messages[0].content


def test_knowledge_block_is_its_own_message_not_mixed_into_system() -> None:
    """spec R-8: Knowledge 블록은 system 메시지에 섞이지 않고, system 다음·
    conversation 앞의 독립된 메시지 하나(`role=\"user\"`)로 들어갑니다. `trust=
    untrusted` 와 출처가 달립니다."""
    system_prompt = "You are a careful assistant."
    search = FakeKnowledgeSearch(
        (SearchResult(source_path="doc.txt", chunk_index=2, content="the fact", score=0.1),)
    )
    usecase = _usecase(search)
    request = CompileContextRequest(
        system_prompt=system_prompt,
        budget_tokens=10_000,
        conversation=(ContextMessage(role="user", content="what is the fact?"),),
        knowledge_sets=("docs",),
    )
    result = usecase(request)

    assert result.messages[0].role == "system"
    assert result.messages[0].content == system_prompt  # 섞이지 않음

    assert result.messages[1].role == "user"
    assert "trust=untrusted" in result.messages[1].content
    assert "source=doc.txt" in result.messages[1].content
    assert "chunk=2" in result.messages[1].content
    assert "the fact" in result.messages[1].content

    assert result.messages[2].content == "what is the fact?"

    knowledge_source_tokens = [s for s in result.report.source_tokens if s.source == "knowledge"]
    assert len(knowledge_source_tokens) == 1
    assert knowledge_source_tokens[0].tokens > 0


def test_budget_overflow_drops_knowledge_between_conversation_and_tools_d7_order() -> None:
    """spec D-7: 예산 초과 시 순서는 (1) 오래된 대화 → (2) Knowledge 하위 순위
    (score 가 큰 것부터) → (3) 도구 스키마의 description. 대화·도구 없이 Knowledge
    만으로도 하위 순위가 먼저 빠지는지 봅니다."""
    search = FakeKnowledgeSearch(
        (
            SearchResult(source_path="best.txt", chunk_index=0, content="x" * 50, score=0.1),
            SearchResult(source_path="worst.txt", chunk_index=0, content="y" * 50, score=0.9),
        )
    )
    usecase = _usecase(search)

    full_request = CompileContextRequest(
        system_prompt="s",
        budget_tokens=10_000,
        conversation=(ContextMessage(role="user", content="q"),),
        knowledge_sets=("docs",),
    )
    full_result = usecase(full_request)
    # system + knowledge(best+worst 둘 다) + conversation 의 총량보다 조금 작은
    # 예산으로 줄여 Knowledge 만 줄어들게 만듭니다.
    tight_budget = full_result.report.total_tokens - 1

    tight_request = CompileContextRequest(
        system_prompt="s",
        budget_tokens=tight_budget,
        conversation=(ContextMessage(role="user", content="q"),),
        knowledge_sets=("docs",),
    )
    result = usecase(tight_request)

    assert result.report.total_tokens <= tight_budget
    dropped_sources = [d.source for d in result.report.dropped]
    assert "knowledge" in dropped_sources

    knowledge_messages = [m for m in result.messages if "[knowledge " in m.content]
    assert len(knowledge_messages) == 1
    # 가장 거리가 먼(score 가 큰) worst 가 먼저 빠지고 best 는 남습니다.
    assert "source=best.txt" in knowledge_messages[0].content
    assert "source=worst.txt" not in knowledge_messages[0].content


def test_budget_overflow_drop_order_is_conversation_then_knowledge_then_tools() -> None:
    """spec D-7: 대화·Knowledge·도구가 모두 있을 때도 순서는 (1) 오래된 대화 →
    (2) Knowledge → (3) 도구 설명입니다."""
    search = FakeKnowledgeSearch(
        (SearchResult(source_path="doc.txt", chunk_index=0, content="z" * 50, score=0.1),)
    )
    usecase = _usecase(search)

    conversation = tuple(
        ContextMessage(role="user" if i % 2 == 0 else "assistant", content=f"message {i} " * 20)
        for i in range(12)
    )
    tools = (ContextToolSchema(name="t1", description="d" * 200, input_schema={}),)

    full_request = CompileContextRequest(
        system_prompt="s",
        budget_tokens=10_000,
        conversation=conversation,
        tools=tools,
        knowledge_sets=("docs",),
    )
    full_result = usecase(full_request)
    budget = full_result.report.total_tokens // 2

    request = CompileContextRequest(
        system_prompt="s",
        budget_tokens=budget,
        conversation=conversation,
        tools=tools,
        knowledge_sets=("docs",),
    )
    result = usecase(request)

    assert result.report.total_tokens <= budget
    dropped_sources = [d.source for d in result.report.dropped]
    if "conversation" in dropped_sources and "knowledge" in dropped_sources:
        assert dropped_sources.index("conversation") < dropped_sources.index("knowledge")
    if "knowledge" in dropped_sources and "tools" in dropped_sources:
        assert dropped_sources.index("knowledge") < dropped_sources.index("tools")
