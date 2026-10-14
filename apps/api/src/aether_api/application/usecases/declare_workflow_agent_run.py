"""spec 0005 2.5 개정 3 (P4-2a B1): `DeclareWorkflowAgentRunUseCase` — 주어진 id 로 선언 →
**실행이 아직 시작되지 않았으면** 통지.

통지 조건이 "새로 만들어졌을 때" 가 아닌 이유(2026-10-14 리뷰): 선언은 커밋됐는데 `XADD` 가
실패하면(Redis 장애) 소비자는 ack 하지 않고 같은 메시지를 다시 받습니다. 그때 "이미 있으니
통지하지 않는다" 로 끝내면 자식 Run 이 `queued` 로 **영원히** 남고, 그것을 기다리는 Workflow
Run 은 `waiting_run` 으로 영원히 파킹됩니다 — 스위퍼도 구하지 못합니다(스위퍼는 자식이
**종결**됐는지를 보고, `queued` 는 종결이 아닙니다). 대기 장치의 침묵을 만들지 않습니다
(`improvement-log/2026-10-11-001`).

그래서 판정은 **상태**로 합니다: 새로 만들었거나, 이미 있고 아직 `queued` 면 통지합니다.
`running` 이후면 통지하지 않습니다 — 이미 누군가 집었고, 중복 통지는 그 worker 의 lease 와
부딪혀 PEL 에 남을 뿐입니다. 셋 다 같은 결과(`control.runs` 한 행, 실행 한 번)로 수렴합니다.
"""

from __future__ import annotations

from aether_runtime.domain.run import RunStatus

from aether_api.application.ports.outbound.run_declaration_store import RunDeclarationStore
from aether_api.application.ports.outbound.run_notifier import RunNotifier
from aether_api.domain.workflow_agent_run_request import WorkflowAgentRunRequest


class DeclareWorkflowAgentRunUseCase:
    def __init__(self, store: RunDeclarationStore, notifier: RunNotifier) -> None:
        self._store = store
        self._notifier = notifier

    def __call__(self, request: WorkflowAgentRunRequest) -> bool:
        created = self._store.create_with_id(
            request.agent_run_id, request.agent_version_id, request.input, request.requested_by
        )
        if not created and not self._is_still_queued(request):
            return False
        self._notifier.requested(
            request.agent_run_id, request.agent_version_id, request.traceparent
        )
        return created

    def _is_still_queued(self, request: WorkflowAgentRunRequest) -> bool:
        """재전달입니다 — 통지가 유실된 적이 있는지는 상태로만 알 수 있습니다.

        `get` 이 아니라 `status` 를 쓰는 이유는 포트의 docstring 에 있습니다 — 자식 Run 은
        `requested_by` 가 비어 있을 수 있고 `RunView` 는 그 값을 필수로 요구합니다.
        """
        return self._store.status(request.agent_run_id) is RunStatus.QUEUED
