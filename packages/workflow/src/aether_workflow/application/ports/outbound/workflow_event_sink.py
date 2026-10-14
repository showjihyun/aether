"""spec 0005 2.10: `WorkflowEventSink` — Workflow 이벤트 발행.

계약: **같은 `seq` 의 재발행은 성공으로 취급**합니다(재개). `EventSink`(Agent Run)와 같은
계약이지만 **다른 포트**입니다 — 어휘가 다릅니다(D-13).
"""

from __future__ import annotations

from typing import Protocol

from aether_workflow.domain.events import WorkflowEvent


class WorkflowEventSink(Protocol):
    def publish(self, event: WorkflowEvent) -> None: ...
