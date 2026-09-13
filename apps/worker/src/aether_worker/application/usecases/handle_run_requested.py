"""spec 0002 2.1, 2.4, 2.18, D-10 (P1-5a): `HandleRunRequestedUseCase` —
`HandleRunRequested` 의 구현. worker 의 소비자(`adapters/inbound/stream`)가 부르는
유일한 문입니다.

**ack 규칙(2.4).**

- 성공(어떤 `RunStatus` 로든 `ExecuteRun` 이 정상 반환) → ack.
- `LeaseHeld`(다른 worker 가 이 Run 의 실행 권한을 이미 쥐고 있음, D-10) → ack 하지
  않습니다 — 메시지는 PEL 에 남고, 다음 `XAUTOCLAIM` 주기가 다시 봅니다.
- 선언 없음(`ExecuteRunUseCase.__call__` 이 내는 `RuntimeError`) → 독약 메시지이므로
  WARNING 로그를 남기고 ack 합니다 — ack 하지 않으면 같은 메시지가 영원히 PEL 에
  남아 재시도를 반복합니다.
- 그 밖의 예외는 흡수하지 않고 그대로 올립니다 — 소비자가 ack 하지 않아 다음
  `XAUTOCLAIM` 이 재시도하게 둡니다.
"""

from __future__ import annotations

import logging

from aether_runtime.application.ports.inbound.execute_run import ExecuteRun
from aether_runtime.domain.run import LeaseHeld

from aether_worker.application.ports.inbound.handle_run_requested import (
    HandleOutcome,
    RequestedMessage,
)
from aether_worker.application.ports.outbound.trace_context import TraceContext

logger = logging.getLogger(__name__)


class HandleRunRequestedUseCase:
    """`HandleRunRequested` 의 구현(spec 0002 2.1, 2.4)."""

    def __init__(self, execute_run: ExecuteRun, trace_context: TraceContext) -> None:
        self._execute_run = execute_run
        self._trace_context = trace_context

    def __call__(self, message: RequestedMessage) -> HandleOutcome:
        with self._trace_context.activate(message.traceparent):
            try:
                status = self._execute_run(message.run_id)
            except LeaseHeld:
                return HandleOutcome(ack=False, status=None)
            except RuntimeError:
                logger.warning(
                    "worker.handle_run_requested.no_declaration",
                    extra={"run_id": str(message.run_id)},
                )
                return HandleOutcome(ack=True, status=None)
        return HandleOutcome(ack=True, status=status)
