"""spec 0004 2.2, 2.3, D-8: `aether_context` 자신의 메시지 값 타입.

`aether_runtime.domain.run.Message` 와 같은 모양이지만, AR-3(`aether_context` 는
`aether_runtime` 을 import 하지 않습니다) 때문에 그 타입을 직접 쓰지 않고 이
패키지만의 값 타입을 따로 둡니다 — `aether_runtime.adapters.outbound.
context_compiler` 의 어댑터가 양쪽을 변환합니다. 표준 `dataclass` 를 씁니다(AR-9).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Role = Literal["system", "user", "assistant", "tool"]


@dataclass(frozen=True)
class ContextMessage:
    """모델에 오가는 메시지 하나. `tool_call_id` 는 `role == "tool"` 일 때만 채워집니다."""

    role: Role
    content: str
    tool_call_id: str | None = None
