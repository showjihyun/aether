"""`BackoffPolicy` 단위 테스트 — 순수 규칙. 시계·sleep·난수를 쓰지 않습니다."""

from __future__ import annotations

import pytest
from aether_worker.domain.backoff import BackoffPolicy


def test_delay_grows_exponentially_and_caps_at_max_delay() -> None:
    policy = BackoffPolicy(max_attempts=10, base_delay=0.5, max_delay=8.0)

    delays = [policy.delay_for(attempt) for attempt in range(1, 8)]

    assert delays == [0.5, 1.0, 2.0, 4.0, 8.0, 8.0, 8.0]


def test_delay_for_first_attempt_equals_base_delay() -> None:
    policy = BackoffPolicy(max_attempts=5, base_delay=0.3, max_delay=10.0)

    assert policy.delay_for(1) == pytest.approx(0.3)


def test_delay_for_rejects_attempt_below_one() -> None:
    policy = BackoffPolicy(max_attempts=5, base_delay=0.5, max_delay=8.0)

    with pytest.raises(ValueError):
        policy.delay_for(0)


def test_should_retry_true_below_max_attempts() -> None:
    policy = BackoffPolicy(max_attempts=3, base_delay=0.1, max_delay=1.0)

    assert policy.should_retry(1) is True
    assert policy.should_retry(2) is True


def test_should_retry_false_once_max_attempts_reached() -> None:
    policy = BackoffPolicy(max_attempts=3, base_delay=0.1, max_delay=1.0)

    assert policy.should_retry(3) is False


def test_delay_for_applies_injected_jitter_deterministically() -> None:
    policy = BackoffPolicy(max_attempts=5, base_delay=1.0, max_delay=10.0)

    delay = policy.delay_for(2, jitter=lambda: 0.25)

    assert delay == pytest.approx(2.25)


def test_delay_for_jitter_is_applied_after_the_cap() -> None:
    policy = BackoffPolicy(max_attempts=10, base_delay=1.0, max_delay=2.0)

    delay = policy.delay_for(5, jitter=lambda: 0.1)

    assert delay == pytest.approx(2.1)
