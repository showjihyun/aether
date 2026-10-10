"""spec 0004 2.1, 2.6, D-5, C-5 (P3-4): `MemoryWriter` — runtime 이 Run 종결 시 Agent 의
기억을 남기는 **유일한** outbound 포트.

`ContextCompiler`·`ToolGateway` 와 같은 자리입니다: 이 포트는 `aether_memory` 를 import
하지 않고 자기 시그니처만 선언합니다. worker 의 `main` 이 `aether_memory` 의 쓰기
유스케이스(구조적으로 호환되는 `write(agent_id, run_id, content)`)를 꽂습니다(AR-10).

계약: Executor 가 **명시적으로 넘긴 것만** 씁니다(요약·자동 승격 없음). 이 포트가 던진
예외는 Run 의 결과를 바꾸지 않습니다 — Memory 는 부산물입니다(`ExecuteRunUseCase` 가
삼키고 경고만 남김).
"""

from __future__ import annotations

from typing import Protocol
from uuid import UUID


class MemoryWriter(Protocol):
    def write(self, agent_id: UUID, run_id: UUID, content: str) -> None:
        """`agent_id` 의 기억으로 `content` 를 그대로 한 건 남깁니다."""
        ...
