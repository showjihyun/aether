"""spec 0002 2.2, 2.4, 2.9, 2.18, D-9: `RequestRun` 포트의 구현 — 버전 결정 →
선언(커밋) → 통지.

버전 결정: `agent_version` 이 없으면 `agent.current_version`, 있으면
`AgentRepository.get_version` 으로 존재를 확인합니다(없으면 `AgentVersionNotFound`).
선언은 `RunDeclarationStore.create` 가 커밋까지 끝냅니다. 그 뒤 `RunNotifier.requested`
가 실패해도(예: Redis 장애) `202` 를 막지 않습니다 — WARNING 을 남기고 그대로
`RunView` 를 반환합니다(spec 2.2, C-2 — Run 은 `queued` 로 남아 관측 가능합니다).

`tracing`(P1-8, `RequestTracing` 포트)이 있으면 선언·통지를 `run.request` span
안에서 하고, 그 span 이 낸 `traceparent`(2.9)를 통지에 실어 worker 가 부모로
삼습니다. `tracing` 을 넘기지 않으면(기존 호출부) 내부 no-op 을 써서 기존과 같이
`traceparent=None` 을 보냅니다 — `RunNotifier`(Redis 구현)가 와이어 위에서는 빈
문자열로 채웁니다(2.18 필드 계약).
"""

from __future__ import annotations

import logging
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from uuid import UUID

from aether_api.application.ports.outbound.agent_repository import AgentRepository
from aether_api.application.ports.outbound.request_tracing import RequestTracing
from aether_api.application.ports.outbound.run_declaration_store import RunDeclarationStore
from aether_api.application.ports.outbound.run_notifier import RunNotifier
from aether_api.domain.run import RunView

logger = logging.getLogger(__name__)


class _NoopRequestTracing:
    """`RequestTracing` 의 내부 no-op — `tracing` 을 넘기지 않은 기존 호출부가
    바뀌지 않게 합니다(`traceparent` 는 항상 `None`)."""

    @contextmanager
    def span(self, name: str, attributes: Mapping[str, str]) -> Iterator[None]:
        del name, attributes
        yield

    def current_traceparent(self) -> str | None:
        return None


class RequestRunUseCase:
    """`AgentRepository`·`RunDeclarationStore`·`RunNotifier`·`RequestTracing` 으로
    inbound 포트 `RequestRun` 을 구현합니다."""

    def __init__(
        self,
        agents: AgentRepository,
        store: RunDeclarationStore,
        notifier: RunNotifier,
        *,
        tracing: RequestTracing | None = None,
    ) -> None:
        self._agents = agents
        self._store = store
        self._notifier = notifier
        self._tracing: RequestTracing = tracing if tracing is not None else _NoopRequestTracing()

    def __call__(
        self, agent_id: UUID, input: str, agent_version: int | None, requested_by: UUID
    ) -> RunView:
        agent = self._agents.get(agent_id)  # 없으면 AgentNotFound (그대로 전파)
        version_number = agent_version if agent_version is not None else agent.current_version
        version = self._agents.get_version(agent_id, version_number)  # 없으면 AgentVersionNotFound

        with self._tracing.span(
            "run.request",
            {"aether.agent_id": str(agent_id), "aether.agent_version_id": str(version.id)},
        ):
            view = self._store.create(agent_id, version.id, version_number, input, requested_by)
            traceparent = self._tracing.current_traceparent()

            try:
                self._notifier.requested(view.run_id, version.id, traceparent)
            except Exception:  # noqa: BLE001 -- XADD 실패는 WARNING 만, 202 는 막지 않습니다(spec 2.2)
                logger.warning(
                    "run.requested.notify_failed",
                    extra={"run_id": str(view.run_id), "agent_version_id": str(version.id)},
                )

        return view
