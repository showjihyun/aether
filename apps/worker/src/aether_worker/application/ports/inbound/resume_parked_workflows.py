"""spec 0005 2.5 개정 3 (P4-2a B2): `ResumeParkedWorkflows` -- 파킹된 Workflow Run 을 깨우는 inbound
포트. 빠른 경로(종결 통지 소비자)와 안전망(스위퍼)이 이 포트 타입만 보고 부릅니다(AR-12).
"""

from __future__ import annotations

from typing import Protocol
from uuid import UUID


class ResumeParkedWorkflows(Protocol):
    def on_agent_run_finished(self, agent_run_id: UUID) -> int:
        """`agent_run_id` 가 종결했다 - 그것을 기다리는 Workflow Run 을 재큐하고 몇 건인지
        돌려줍니다."""
        ...

    def sweep(self) -> int:
        """기다리는 자식이 이미 종결인 Workflow Run 을 전부 재큐하고 몇 건인지 돌려줍니다."""
        ...
