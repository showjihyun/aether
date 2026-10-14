"""spec 0005 2.5 개정 3, C-2 (P4-2a B2): `WorkflowSweeper` - 파킹 스위퍼(안전망). 낮은 빈도로
`ResumeParkedWorkflows.sweep()` 을 부릅니다.

`heartbeat` 스레드와 같은 모양(`stop.wait(interval)`)이고 **`sweep_once()` 를 따로 부를 수 있어**
테스트가 시간을 기다리지 않습니다. 시작하자마자 한 번 훑습니다 - 재시작 직후 놓친 신호를 한 주기
기다리지 않고 주워 담습니다.

**침묵은 변화 없음의 증거가 아닙니다**(`improvement-log/2026-10-11-001`): 한 번의 DB·Redis 장애가
스레드를 죽이면 안전망이 소리 없이 사라지고, 그 뒤로는 놓친 신호를 아무도 구하지 않습니다. 그래서
실패는 `ERROR` 로그로 남기고 **다음 주기에 다시 시도**합니다. 재큐가 있었으면 건수를 `INFO` 로
남깁니다(0건인 주기는 소음이라 남기지 않습니다).
"""

from __future__ import annotations

import logging
from threading import Event

from aether_worker.application.ports.inbound.resume_parked_workflows import ResumeParkedWorkflows

logger = logging.getLogger(__name__)


class WorkflowSweeper:
    def __init__(self, resume: ResumeParkedWorkflows, *, interval_seconds: float) -> None:
        self._resume = resume
        self._interval_seconds = interval_seconds

    def sweep_once(self) -> int:
        """한 번 훑고 재큐한 건수를 돌려줍니다. 예외는 호출자(테스트)에게 그대로 올립니다."""
        requeued = self._resume.sweep()
        if requeued:
            logger.info("worker.workflow_sweeper.requeued", extra={"count": requeued})
        return requeued

    def run_until(self, stop: Event) -> None:
        while not stop.is_set():
            try:
                self.sweep_once()
            except Exception:  # noqa: BLE001 - 안전망 스레드는 죽지 않는다, 다음 주기에 다시 시도
                logger.exception("worker.workflow_sweeper.sweep_failed")
            stop.wait(self._interval_seconds)
