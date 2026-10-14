"""spec 0005 2.5 개정 3 (P4-2a B1): `DeclareWorkflowAgentRun` 인바운드 포트.

스트림 소비자(`adapters/inbound/stream/workflow_agent_run_consumer.py`)는 이 포트 타입만 보고
부릅니다(AR-12) — 구현은 조립(`main.py`)이 건네줍니다.
"""

from __future__ import annotations

from typing import Protocol

from aether_api.domain.workflow_agent_run_request import WorkflowAgentRunRequest


class DeclareWorkflowAgentRun(Protocol):
    """`request.agent_run_id` 로 `control.runs` 선언을 만들고 `aether:runs:requested` 로 통지합니다.

    새로 만들어 통지했으면 `True`, 이미 있던 Run 이면(멱등 재전달) `False` — 이 경우 통지하지
    않습니다(같은 Run 이 두 번 실행 요청되지 않도록). 소비자는 어느 쪽이든 ack 합니다. 선언이나
    통지가 실패하면 예외를 그대로 올립니다(삼키지 않습니다).
    """

    def __call__(self, request: WorkflowAgentRunRequest) -> bool: ...
