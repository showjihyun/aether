"""spec 0002 2.1, 2.2, D-9, D-11: Run 유스케이스 인터페이스.

HTTP 어댑터(`adapters/inbound/http/runs.py`)는 이 포트 타입만 보고 부릅니다(AR-12) —
구현(`application/usecases/*.py`)은 조립(`main.py`)이 건네줍니다.
"""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from aether_api.domain.run import RunView


class RequestRun(Protocol):
    """`agent_id` 의 Agent 를 실행합니다 — `agent_version` 이 없으면 현재 버전.

    Agent 가 없으면 `AgentNotFound`, 지정한 버전이 없으면 `AgentVersionNotFound` 를
    던집니다(spec 2.2).
    """

    def __call__(
        self, agent_id: UUID, input: str, agent_version: int | None, requested_by: UUID
    ) -> RunView: ...


class GetRun(Protocol):
    """Run 의 투영을 돌려줍니다. 없으면 `RunNotFound` 를 던집니다(spec 0001 D-11)."""

    def __call__(self, run_id: UUID) -> RunView: ...


class CancelRun(Protocol):
    """`cancel_requested_at` 을 멱등으로 설정합니다. 없으면 `RunNotFound` 를 던집니다.

    Run 이 이미 종결이어도 현재 상태로 돌려줍니다(spec 2.2, D-11).
    """

    def __call__(self, run_id: UUID) -> RunView: ...
