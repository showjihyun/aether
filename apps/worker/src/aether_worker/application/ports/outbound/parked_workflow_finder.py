"""spec 0005 2.5 개정 3 (P4-2a B2): `ParkedWorkflowFinder` -- 파킹된 Workflow Run 을 **찾기만**
합니다.

재큐에 필요한 `workflow_version_id` 를 같은 조회에서 함께 돌려줍니다(요청 스트림의 계약이
`workflow_run_id` 와 `workflow_version_id` 둘이라, 따로 읽으면 왕복이 한 번 더 듭니다).
어댑터는 `data.workflow_run_executions` + `data.run_executions`(둘 다 worker 가 소유하는 평면)와
`control.workflow_runs`(SELECT 만)를 읽습니다. 쓰지 않습니다.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID


@dataclass(frozen=True)
class ParkedWorkflow:
    workflow_run_id: UUID
    workflow_version_id: UUID


class ParkedWorkflowFinder(Protocol):
    def waiting_on(self, agent_run_id: UUID) -> tuple[ParkedWorkflow, ...]:
        """`status = waiting_run` 이고 `waiting_run_id = agent_run_id` 인 Workflow Run. 빠른 경로가
        종결 통지 하나마다 부릅니다 - 대부분(평범한 Agent Run)은 빈 결과입니다."""
        ...

    def ready_to_resume(self) -> tuple[ParkedWorkflow, ...]:
        """재개할 수 있는 파킹 Workflow Run 전부 - 한 번의 조회(JOIN)입니다. 셋을 줍습니다:
        `status = waiting_run` 이고 기다리는 자식이 **이미 종결**인 것, 그리고
        `status = waiting_approval` 이고 기다리는 노드 실행의 **승인이 이미 저장된** 것
        (P4-4), 그리고 `status = waiting_timer` 이고 `wake_at` 이 **이미 지난** 것(P4-3 - `WAIT`
        에는 깨우는 외부 사건이 없어 이것이 주 경로입니다). 스위퍼가 부릅니다. 자식의 실행 행이
        아직 없는 것(worker 가 집지 않음)은 종결이 아니므로 줍지 않습니다."""
        ...
