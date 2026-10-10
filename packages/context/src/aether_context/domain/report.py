"""spec 0004 2.3, D-11: `ContextReport` — 무엇을 넣고 뺐는가.

본문을 넣지 않습니다 — 숫자와 종류만입니다(D-11, spec 0003 D-12 와 같은 이유).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

SourceName = Literal["system", "conversation", "knowledge", "memory", "tools"]
"""D-7 의 제거 순서가 참조하는 다섯 소스 이름. `system`·`conversation`·`tools`
(P3-1), `knowledge`(P3-3), `memory`(P3-4) 모두 실제로 채워집니다. 해당 소스가 비어 있으면
`source_tokens` 에 나타나지 않습니다."""


@dataclass(frozen=True)
class SourceTokens:
    """소스 하나의 (드롭 적용 전) 토큰 추정."""

    source: SourceName
    tokens: int


@dataclass(frozen=True)
class DroppedSource:
    """예산 초과로 뺀 소스 하나와 그 양(토큰)."""

    source: SourceName
    tokens: int


@dataclass(frozen=True)
class ContextReport:
    """조립 결과와 함께 돌아가는 보고 — R-2·R-11 의 판정 대상.

    `dropped` 는 D-7 의 순서(Memory → 오래된 대화 → Knowledge 하위 순위 → 도구
    스키마의 설명)대로 쌓입니다. 빈 튜플이면 아무것도 빼지 않았다는 뜻입니다.
    """

    budget_tokens: int
    source_tokens: tuple[SourceTokens, ...]
    total_tokens: int
    dropped: tuple[DroppedSource, ...] = field(default_factory=tuple)
