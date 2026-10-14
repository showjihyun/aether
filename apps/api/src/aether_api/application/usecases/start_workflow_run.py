"""spec 0005 2.2, 2.3, 2.9 개정 2: `StartWorkflowRun` 포트의 구현 — Version 결정 → 선언(커밋) →
통지.

Version 결정: `workflow_version` 이 없으면 `workflow.current_version`, 있으면
`WorkflowRepository.get_version` 으로 존재를 확인합니다(없으면 `WorkflowVersionNotFound`).
선언은 `WorkflowRunDeclarationStore.create` 가 커밋까지 끝냅니다. 그 뒤
`WorkflowRunNotifier.requested` 가 실패해도 `202` 를 막지 않습니다 — WARNING 을 남기고 그대로
`WorkflowRunView` 를 반환합니다(`request_run.py` 와 같은 규칙, Run 은 `queued` 로 남아 관측
가능합니다).

`tracing` 이 있으면 선언·통지를 `workflow_run.request` span 안에서 하고 그 span 이 낸
`traceparent` 를 통지에 실어 worker 가 부모로 삼습니다. 넘기지 않으면 내부 no-op 을 써서
`traceparent=None` 을 보냅니다(와이어 위에서는 빈 문자열).
"""

from __future__ import annotations

import logging
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from typing import Any
from uuid import UUID

from aether_api.application.ports.outbound.request_tracing import RequestTracing
from aether_api.application.ports.outbound.workflow_repository import WorkflowRepository
from aether_api.application.ports.outbound.workflow_run_declaration_store import (
    WorkflowRunDeclarationStore,
)
from aether_api.application.ports.outbound.workflow_run_notifier import WorkflowRunNotifier
from aether_api.domain.workflow import WorkflowNotFound, WorkflowVersionNotFound
from aether_api.domain.workflow_run import WorkflowRunView

logger = logging.getLogger(__name__)


class _NoopRequestTracing:
    """`RequestTracing` 의 내부 no-op — `tracing` 을 넘기지 않으면 `traceparent` 는 `None`."""

    @contextmanager
    def span(self, name: str, attributes: Mapping[str, str]) -> Iterator[None]:
        del name, attributes
        yield

    def current_traceparent(self) -> str | None:
        return None


class StartWorkflowRunUseCase:
    """`WorkflowRepository`·`WorkflowRunDeclarationStore`·`WorkflowRunNotifier`·
    `RequestTracing` 으로 inbound 포트 `StartWorkflowRun` 을 구현합니다."""

    def __init__(
        self,
        workflows: WorkflowRepository,
        store: WorkflowRunDeclarationStore,
        notifier: WorkflowRunNotifier,
        *,
        tracing: RequestTracing | None = None,
    ) -> None:
        self._workflows = workflows
        self._store = store
        self._notifier = notifier
        self._tracing: RequestTracing = tracing if tracing is not None else _NoopRequestTracing()

    def __call__(
        self,
        workflow_id: UUID,
        input: dict[str, Any] | None,
        workflow_version: int | None,
        requested_by: UUID,
    ) -> WorkflowRunView:
        workflow = self._workflows.get(workflow_id)
        if workflow is None:
            raise WorkflowNotFound(workflow_id)
        if workflow_version is None:
            number = workflow.latest_version.number
        else:
            if self._workflows.get_version(workflow_id, workflow_version) is None:
                raise WorkflowVersionNotFound(workflow_id, workflow_version)
            number = workflow_version

        with self._tracing.span(
            "workflow_run.request",
            {"aether.workflow_id": str(workflow_id), "aether.workflow_version": str(number)},
        ):
            view = self._store.create(workflow_id, number, input, requested_by)
            traceparent = self._tracing.current_traceparent()

            try:
                self._notifier.requested(
                    view.workflow_run_id, view.workflow_version_id, traceparent
                )
            except Exception:  # noqa: BLE001 -- XADD 실패는 WARNING 만, 202 는 막지 않습니다
                logger.warning(
                    "workflow_run.requested.notify_failed",
                    extra={
                        "workflow_run_id": str(view.workflow_run_id),
                        "workflow_version_id": str(view.workflow_version_id),
                    },
                )

        return view
