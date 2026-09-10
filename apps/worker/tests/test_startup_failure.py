"""`connect_with_backoff` 단위 테스트 — 컨테이너 없음. `make_client`·`sleep` 은 fake.

`serve()` 전체(Settings·telemetry 포함)가 아니라 `connect_with_backoff` 만 검사합니다 —
Redis 가 없을 때 정확히 `max_attempts` 번 시도하고 0 이 아닌 결과(예외)를 내는 것이
이 단위의 핵심 계약이고, 그 계약은 telemetry 나 consumer group 과 무관합니다.
"""

from __future__ import annotations

import pytest
from aether_worker.domain.backoff import BackoffPolicy
from aether_worker.main import WorkerStartupError, connect_with_backoff


def test_connect_with_backoff_retries_exactly_max_attempts_then_raises(
    caplog: pytest.LogCaptureFixture,
) -> None:
    policy = BackoffPolicy(max_attempts=4, base_delay=0.01, max_delay=0.05)
    attempts = 0
    sleeps: list[float] = []

    def failing_make_client() -> object:
        nonlocal attempts
        attempts += 1
        raise ConnectionError("boom")

    with caplog.at_level("WARNING"):
        with pytest.raises(WorkerStartupError) as exc_info:
            connect_with_backoff(failing_make_client, policy, sleeps.append)

    assert attempts == policy.max_attempts
    assert len(sleeps) == policy.max_attempts - 1
    assert "boom" in str(exc_info.value)
    assert "4" in str(exc_info.value)


def test_connect_with_backoff_sleeps_use_the_policys_delays() -> None:
    policy = BackoffPolicy(max_attempts=3, base_delay=0.1, max_delay=1.0)
    sleeps: list[float] = []

    def failing_make_client() -> object:
        raise TimeoutError("no route to host")

    with pytest.raises(WorkerStartupError):
        connect_with_backoff(failing_make_client, policy, sleeps.append)

    assert sleeps == pytest.approx([0.1, 0.2])


def test_connect_with_backoff_returns_the_client_on_first_success() -> None:
    policy = BackoffPolicy(max_attempts=5, base_delay=0.01, max_delay=0.05)
    sleeps: list[float] = []
    sentinel = object()

    result = connect_with_backoff(lambda: sentinel, policy, sleeps.append)

    assert result is sentinel
    assert sleeps == []


def test_connect_with_backoff_succeeds_after_transient_failures() -> None:
    policy = BackoffPolicy(max_attempts=5, base_delay=0.01, max_delay=0.05)
    sleeps: list[float] = []
    attempts = 0
    sentinel = object()

    def flaky_make_client() -> object:
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise ConnectionError("not ready yet")
        return sentinel

    result = connect_with_backoff(flaky_make_client, policy, sleeps.append)

    assert result is sentinel
    assert attempts == 3
    assert len(sleeps) == 2
