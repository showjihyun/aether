"""spec 0002 2.1, R-4 (P1-5a): `SystemClock` — 프로덕션 `Clock` 어댑터.

`sleep()` 은 여기서 호출하지 않습니다 — 실제로 기다리게 되어 R-11(결정적 테스트)을
어기고, `tests/arch/test_no_sleep_in_tests.py` 가 금지하는 것과 같은 종류의 실제
대기를 테스트에 들이는 일이기 때문입니다.
"""

from __future__ import annotations

from datetime import UTC

from aether_runtime.adapters.outbound.system_clock import SystemClock


def test_now_is_timezone_aware_utc() -> None:
    clock = SystemClock()

    now = clock.now()

    assert now.tzinfo is not None
    assert now.utcoffset() == UTC.utcoffset(None)


def test_monotonic_does_not_go_backwards_across_calls() -> None:
    clock = SystemClock()

    first = clock.monotonic()
    second = clock.monotonic()

    assert second >= first
