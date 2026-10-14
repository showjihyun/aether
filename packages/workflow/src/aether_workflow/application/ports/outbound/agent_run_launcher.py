"""spec 0005 2.5 개정 3, 2.9 개정 2 (P4-2a B2): `AgentRunLauncher` - 자식 Agent Run 의 **선언을
요청**합니다.

worker 는 `control.runs` 에 INSERT 할 수 없으므로(0001 GRANT) 실행기가 자식 Run 의 id 를 **정해서**
이 포트로 api 에 싣고, api 가 그 id 로 선언을 만들어 `aether:runs:requested` 에 통지합니다. 같은
요청이 두 번 가도 선언은 한 행입니다(R-8) - 그래서 이 포트의 `launch` 는 **재호출해도 안전**합니다.
호출자(`AdvanceWorkflowRunUseCase`)는 `agent_run_id` 를 노드 실행 행에 **영속한 뒤에** 부릅니다.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID


@dataclass(frozen=True)
class AgentRunLaunch:
    """`aether:workflow:agent_runs:requested` 한 항목의 내용 - 필드 이름이 계약입니다.

    `input` 은 Workflow Run 의 `input` 을 직렬화한 문자열입니다(노드 출력을 다음 노드의 입력으로
    잇는 것은 P4-2b). `requested_by` 는 Workflow 를 시작한 주체로, 자식 Run 이 그대로 물려받습니다.
    """

    agent_run_id: UUID
    agent_version_id: UUID
    input: str
    requested_by: UUID
    traceparent: str | None


class AgentRunLauncher(Protocol):
    def launch(self, request: AgentRunLaunch) -> None:
        """요청을 싣습니다. 실패하면 예외를 올립니다(삼키지 않습니다) - 호출자의 메시지는 ack 되지
        않고 같은 `agent_run_id` 로 다시 시도됩니다."""
        ...
