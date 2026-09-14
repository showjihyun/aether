"""spec 0002 2.2, 2.18: `RunNotifier` — `aether:runs:requested` 로 가는 실행 통지의
outbound 포트. Control Plane 이 `requested` 스트림에 **쓰기만** 하는 쪽입니다(2.18).
"""

from __future__ import annotations

from typing import Protocol
from uuid import UUID


class RunNotifier(Protocol):
    """`requested(run_id, agent_version_id, traceparent)` — 실패해도 예외를 삼키지
    않습니다. 실패 시 `202` 를 막지 않는 것은 유스케이스(`RequestRunUseCase`)의
    책임입니다(spec 2.2 — 커밋 뒤 XADD, XADD 실패는 WARNING).
    """

    def requested(self, run_id: UUID, agent_version_id: UUID, traceparent: str | None) -> None: ...
