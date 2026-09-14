"""spec 0002 2.4, 2.18, D-2: `ApplyRunStatus` — 투영 소비자(`StatusConsumer`)가 부르는
inbound 포트. `control.runs` 의 `seq` 단조 증가 규칙으로 멱등하게 적용합니다.
"""

from __future__ import annotations

from typing import Protocol

from aether_api.domain.run_status_message import RunStatusMessage


class ApplyRunStatus(Protocol):
    """`message.seq` 가 `control.runs.status_seq` 보다 클 때만 적용합니다.

    적용됐으면 `True`, 이미 적용된(같거나 낮은 `seq`) 메시지면 `False` 를 돌려줍니다 —
    소비자는 어느 쪽이든 ack 합니다(D-2, 멱등 무시).
    """

    def __call__(self, message: RunStatusMessage) -> bool: ...
