"""spec 0002 2.2, 2.4, D-9: `RequestRun` 포트의 구현 — 버전 결정 → 선언(커밋) → 통지.

버전 결정: `agent_version` 이 없으면 `agent.current_version`, 있으면
`AgentRepository.get_version` 으로 존재를 확인합니다(없으면 `AgentVersionNotFound`).
선언은 `RunDeclarationStore.create` 가 커밋까지 끝냅니다. 그 뒤 `RunNotifier.requested`
가 실패해도(예: Redis 장애) `202` 를 막지 않습니다 — WARNING 을 남기고 그대로
`RunView` 를 반환합니다(spec 2.2, C-2 — Run 은 `queued` 로 남아 관측 가능합니다).

api 는 아직 트레이싱이 없으므로(P1-8 이전) `traceparent` 는 `None` 을 보냅니다 —
`RunNotifier`(Redis 구현)가 와이어 위에서는 빈 문자열로 채웁니다(2.18 필드 계약).
"""

from __future__ import annotations

import logging
from uuid import UUID

from aether_api.application.ports.outbound.agent_repository import AgentRepository
from aether_api.application.ports.outbound.run_declaration_store import RunDeclarationStore
from aether_api.application.ports.outbound.run_notifier import RunNotifier
from aether_api.domain.run import RunView

logger = logging.getLogger(__name__)


class RequestRunUseCase:
    """`AgentRepository`·`RunDeclarationStore`·`RunNotifier` 로 inbound 포트
    `RequestRun` 을 구현합니다."""

    def __init__(
        self,
        agents: AgentRepository,
        store: RunDeclarationStore,
        notifier: RunNotifier,
    ) -> None:
        self._agents = agents
        self._store = store
        self._notifier = notifier

    def __call__(
        self, agent_id: UUID, input: str, agent_version: int | None, requested_by: UUID
    ) -> RunView:
        agent = self._agents.get(agent_id)  # 없으면 AgentNotFound (그대로 전파)
        version_number = agent_version if agent_version is not None else agent.current_version
        version = self._agents.get_version(agent_id, version_number)  # 없으면 AgentVersionNotFound

        view = self._store.create(agent_id, version.id, version_number, input, requested_by)

        try:
            self._notifier.requested(view.run_id, version.id, None)
        except Exception:  # noqa: BLE001 -- XADD 실패는 WARNING 만, 202 는 막지 않습니다(spec 2.2)
            logger.warning(
                "run.requested.notify_failed",
                extra={"run_id": str(view.run_id), "agent_version_id": str(version.id)},
            )

        return view
