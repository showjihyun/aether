"""spec 0005: `SystemClock` 는 timezone-aware UTC 를 돌려준다(DB timestamptz 와 섞여도 안전)."""

from __future__ import annotations

from datetime import UTC

from aether_workflow.adapters.outbound.system_clock import SystemClock


def test_now_is_timezone_aware_utc() -> None:
    assert SystemClock().now().tzinfo is UTC
