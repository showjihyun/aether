"""Redis 연결 재시도 지연 규칙 — 순수 규칙(architecture.md 3.1, AR-9).

시계·sleep·난수를 갖지 않습니다. 지연을 계산만 하고, 그것으로 무엇을 하는지(실제로
기다리는 것)는 `main.py` 의 조립이 결정합니다. 표준 라이브러리만 import 합니다.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass


@dataclass(frozen=True)
class BackoffPolicy:
    """지수 백오프 정책.

    `max_attempts` 는 총 시도 횟수(첫 시도 포함)입니다. `base_delay` 는 1번째 실패 뒤의
    지연이고, 매 실패마다 두 배로 늘다가 `max_delay` 에서 멈춥니다.
    """

    max_attempts: int
    base_delay: float
    max_delay: float

    def delay_for(self, attempt: int, *, jitter: Callable[[], float] | None = None) -> float:
        """`attempt`번째 시도가 실패한 뒤 다음 시도 전까지 기다릴 시간(초).

        `attempt` 는 1부터 시작합니다(1 = 첫 번째 시도가 실패했다는 뜻). 결과는
        `base_delay * 2**(attempt-1)` 을 `max_delay` 로 자른 값입니다.

        `jitter` 를 주면 그 함수가 반환하는 초 단위 값을 지연에 더합니다. 난수 자체를
        만들지 않는 것은 의도입니다 — 테스트가 결정적 함수를 주입해 결과를 재현합니다.
        """
        if attempt < 1:
            raise ValueError("attempt must be >= 1")

        exponential: float = self.base_delay * (2.0 ** (attempt - 1))
        delay: float = min(exponential, self.max_delay)
        if jitter is not None:
            delay += jitter()
        return delay

    def should_retry(self, attempt: int) -> bool:
        """`attempt`번째 시도가 실패했을 때, 다시 시도해야 하는가.

        `attempt` 가 `max_attempts` 에 도달했으면(이미 마지막 시도까지 썼으면) False.
        """
        return attempt < self.max_attempts
