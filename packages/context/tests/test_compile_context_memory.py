"""spec 0004 R-10, D-7, D-8, 2.5, 2.6, R-1 (P3-4): Memory 소스를 조립하는
`CompileContextUseCase` 의 계약 테스트. 컨테이너·네트워크 없음(AR-9) —
`MemoryReader` outbound 포트에 fake 를 꽂습니다.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from aether_context.adapters.outbound.token_counter.char_approx import CharApproxTokenCounter
from aether_context.application.ports.inbound.compile_context import CompileContextRequest
from aether_context.application.usecases.compile_context import CompileContextUseCase
from aether_context.domain.knowledge import SearchResult, render_knowledge_block
from aether_context.domain.memory import MemoryHit, render_memory_block
from aether_context.domain.message import ContextMessage

from tests.support.context_fakes import FakeKnowledgeSearch, FakeMemoryReader

_AGENT_ID = uuid.UUID("00000000-0000-0000-0000-0000000000a1")
_CREATED = datetime(2026, 10, 1, 12, 30, 0, tzinfo=UTC)


def _hit(n: int, content: str = "remembered") -> MemoryHit:
    return MemoryHit(
        id=uuid.UUID(f"00000000-0000-0000-0000-{n:012d}"),
        content=content,
        created_at=_CREATED,
        score=0.1 * n,
    )


def _usecase(
    reader: FakeMemoryReader | None, knowledge: FakeKnowledgeSearch | None = None
) -> CompileContextUseCase:
    return CompileContextUseCase(CharApproxTokenCounter(), knowledge, reader)


def _request(**overrides: object) -> CompileContextRequest:
    base: dict[str, object] = {
        "system_prompt": "SYS",
        "budget_tokens": 10_000,
        "conversation": (ContextMessage(role="user", content="what did we do?"),),
        "agent_id": _AGENT_ID,
    }
    base.update(overrides)
    return CompileContextRequest(**base)  # type: ignore[arg-type]


def test_memory_block_is_marked_unverified_and_differs_from_knowledge_block() -> None:
    """spec R-10, D-8: Memory 블록은 `verified=false` 표지를 달고, 같은 내용의
    Knowledge 블록과 같은 문자열이 되지 않습니다."""
    hit = _hit(1, "same text")
    block = render_memory_block(hit)
    knowledge = render_knowledge_block(
        SearchResult(source_path="a.txt", chunk_index=0, content="same text", score=0.1)
    )

    assert block.startswith(
        f"[memory id={hit.id} created=2026-10-01T12:30:00+00:00 verified=false]"
    )
    assert block.endswith("[/memory]")
    assert "same text" in block
    assert "trust=untrusted" not in block
    assert block != knowledge
    assert "[knowledge" not in block


def test_memory_enters_as_its_own_message_not_mixed_into_system_or_knowledge() -> None:
    """spec R-10, D-8, 2.5: Memory 는 독립된 메시지 하나 — system 에도 Knowledge
    메시지에도 섞이지 않습니다."""
    reader = FakeMemoryReader((_hit(1, "MEM-ONE"), _hit(2, "MEM-TWO")))
    knowledge = FakeKnowledgeSearch(
        (SearchResult(source_path="k.txt", chunk_index=0, content="KNOW", score=0.1),)
    )
    result = _usecase(reader, knowledge)(_request(knowledge_sets=("docs",)))

    system = [m for m in result.messages if m.role == "system"]
    assert len(system) == 1 and "MEM" not in system[0].content
    memory_messages = [m for m in result.messages if "[memory " in m.content]
    knowledge_messages = [m for m in result.messages if "[knowledge " in m.content]
    assert len(memory_messages) == 1 and len(knowledge_messages) == 1
    assert memory_messages[0] is not knowledge_messages[0]
    assert "KNOW" not in memory_messages[0].content
    assert "MEM-ONE" not in knowledge_messages[0].content
    # 순서는 reader 가 돌려준 그대로(R-1).
    assert memory_messages[0].content.index("MEM-ONE") < memory_messages[0].content.index("MEM-TWO")


def test_memory_is_read_with_last_user_message_and_top_k() -> None:
    """spec 2.5: 질의는 마지막 user 메시지, 상위 k 는 request.memory_top_k."""
    reader = FakeMemoryReader((_hit(1),))
    conversation = (
        ContextMessage(role="user", content="first"),
        ContextMessage(role="assistant", content="a"),
        ContextMessage(role="user", content="LAST-QUERY"),
    )
    _usecase(reader)(_request(conversation=conversation, memory_top_k=7))

    assert reader.calls == [(_AGENT_ID, "LAST-QUERY", 7)]


def test_memory_not_read_without_agent_id() -> None:
    """spec 2.6, P3-4 (b): agent_id 가 None 이면 읽지 않습니다."""
    reader = FakeMemoryReader((_hit(1),))
    # 대조: agent_id 가 있으면 같은 요청이 읽습니다(아래 단언이 우연히 참이 아님을 보임).
    _usecase(reader)(_request())
    assert len(reader.calls) == 1
    reader.calls.clear()

    result = _usecase(reader)(_request(agent_id=None))

    assert reader.calls == []
    assert not any("[memory " in m.content for m in result.messages)
    assert "memory" not in [s.source for s in result.report.source_tokens]


def test_memory_not_read_without_reader_or_user_message() -> None:
    """reader 가 없거나 user 메시지가 없으면 읽지 않고 실패하지도 않습니다."""
    reader = FakeMemoryReader((_hit(1),))
    # 대조: reader 와 user 메시지가 모두 있으면 Memory 블록이 들어갑니다.
    with_both = _usecase(reader)(_request())
    assert any("[memory " in m.content for m in with_both.messages)
    reader.calls.clear()

    no_reader = _usecase(None)(_request())
    assert not any("[memory " in m.content for m in no_reader.messages)

    no_user = _usecase(reader)(_request(conversation=()))
    assert reader.calls == []
    assert not any("[memory " in m.content for m in no_user.messages)


def test_report_has_memory_source_tokens() -> None:
    """spec 2.3: ContextReport.source_tokens 에 memory 가 채워집니다."""
    reader = FakeMemoryReader((_hit(1, "x" * 40),))
    result = _usecase(reader)(_request())

    by_source = {s.source: s.tokens for s in result.report.source_tokens}
    assert by_source["memory"] > 0
    assert result.report.dropped == ()


def test_memory_is_dropped_first_before_old_conversation() -> None:
    """spec D-7: 예산 초과 시 Memory 가 가장 먼저 빠지고, 그것만으로 충분하면 오래된
    대화는 그대로입니다. 뺀 양은 dropped 에 source=memory 로 남습니다."""
    reader = FakeMemoryReader((_hit(1, "m" * 400),))
    conversation = (
        ContextMessage(role="user", content="u" * 40),
        ContextMessage(role="assistant", content="a" * 40),
        ContextMessage(role="user", content="q" * 40),
    )
    full = _usecase(reader)(_request(conversation=conversation))
    memory_tokens = {s.source: s.tokens for s in full.report.source_tokens}["memory"]
    budget = full.report.total_tokens - 1
    assert memory_tokens > 1

    result = _usecase(reader)(_request(conversation=conversation, budget_tokens=budget))

    assert [d.source for d in result.report.dropped] == ["memory"]
    assert result.report.dropped[0].tokens == memory_tokens
    assert not any("[memory " in m.content for m in result.messages)
    assert [m.content for m in result.messages if m.role != "system"] == [
        c.content for c in conversation
    ]
    assert result.report.total_tokens <= budget


def test_memory_drops_before_conversation_when_budget_is_tight() -> None:
    """spec D-7: 더 빠듯하면 Memory 다음에 오래된 대화 — dropped 의 순서가
    memory, conversation 입니다."""
    reader = FakeMemoryReader((_hit(1, "m" * 400),))
    conversation = (
        ContextMessage(role="user", content="u" * 400),
        ContextMessage(role="assistant", content="a" * 40),
        ContextMessage(role="user", content="q" * 40),
    )
    result = _usecase(reader)(_request(conversation=conversation, budget_tokens=40))

    assert [d.source for d in result.report.dropped][:2] == ["memory", "conversation"]


def test_compile_with_memory_is_deterministic_across_100_repeats() -> None:
    """spec R-1: Memory 가 있어도 같은 입력은 같은 출력입니다."""
    reader = FakeMemoryReader((_hit(1), _hit(2), _hit(3)))
    usecase = _usecase(reader)
    first = usecase(_request())
    assert any("[memory " in m.content for m in first.messages)
    for _ in range(100):
        assert usecase(_request()) == first
