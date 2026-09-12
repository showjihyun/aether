"""`sleep` 없이 조건을 기다리는 통합 테스트 전용 헬퍼 (spec 0002 R-11, 2.16).

`tests/arch/test_no_sleep_in_tests.py` 가 `time.sleep`/`asyncio.sleep`/`from time import
sleep` 를 테스트 트리 전체에서 금지합니다 — 기다림은 이 `wait_until` 하나만 씁니다.
내부는 `time.sleep` 대신 `threading.Event().wait(interval)` 로 폴링합니다: 매번 새로
만든(한 번도 `set()` 하지 않는) `Event` 의 `wait(timeout=interval)` 은 그 시간이 지나면
`False` 를 반환하며 돌아오는, `time.sleep` 과 동등한 대기 수단입니다.

단위 테스트는 이 헬퍼를 쓰지 않습니다 — 시간은 전부 주입합니다(2.16, `Clock` 포트).
이 헬퍼는 `integration` 마커 테스트가 Redis/PostgreSQL 투영처럼 다른 프로세스가
비동기로 완성하는 상태를 기다릴 때만 씁니다.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from threading import Event


def wait_until(
    predicate: Callable[[], bool],
    timeout: float,
    interval: float = 0.05,
) -> bool:
    """`predicate()` 가 참이 될 때까지 최대 `timeout` 초 동안 `interval` 초 간격으로 폴링합니다.

    제한 시간 안에 참이 되면 `True`, 아니면 `False` 를 반환합니다 — 무엇을 기다렸는지는
    호출부가 압니다(예: `assert wait_until(..., timeout=5.0), "설명"`).
    """
    deadline = time.monotonic() + timeout
    waiter = Event()
    while True:
        if predicate():
            return True
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return False
        waiter.wait(min(interval, remaining))
