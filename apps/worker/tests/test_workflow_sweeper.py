"""spec 0005 2.5 개정 3, C-2 (P4-2a B2): `WorkflowSweeper` -- 스위퍼 스레드의 모양.

`heartbeat` 와 같은 모양(`stop.wait(interval)`)이고 `sweep_once()` 를 따로 부를 수 있다 -- 테스트가
시간을 기다리지 않는다(`tests/arch/test_no_sleep_in_tests.py`). **침묵은 변화 없음의 증거가 아니다**
(`2026-10-11-001`): 한 번의 실패가 스레드를 죽이면 안전망이 소리 없이 사라지므로, 실패는 로그로
남기고 다음 주기에 다시 시도한다.
"""

from __future__ import annotations

import logging
from threading import Event
from uuid import UUID

import pytest
from aether_worker.adapters.inbound.schedule.workflow_sweeper import WorkflowSweeper


class _Resume:
    def __init__(self, stop: Event | None = None, *, fail_first: bool = False) -> None:
        self.sweeps = 0
        self._stop = stop
        self._fail_first = fail_first

    def on_agent_run_finished(self, agent_run_id: UUID) -> int:
        return 0

    def sweep(self) -> int:
        self.sweeps += 1
        if self._fail_first and self.sweeps == 1:
            raise ConnectionError("db down")
        if self._stop is not None and self.sweeps >= 2:
            self._stop.set()
        return 0


def test_sweep_once_calls_the_use_case_exactly_once() -> None:
    resume = _Resume()

    WorkflowSweeper(resume, interval_seconds=30.0).sweep_once()

    assert resume.sweeps == 1


def test_run_until_does_not_sweep_when_already_stopped() -> None:
    """이미 멈춘 상태로 시작하면 훑지 않고, 주기(3600초)를 기다리지도 않고 돌아온다."""
    stop = Event()
    stop.set()
    resume = _Resume()

    WorkflowSweeper(resume, interval_seconds=3600.0).run_until(stop)

    assert resume.sweeps == 0


def test_run_until_sweeps_right_away_and_then_every_period() -> None:
    """시작하자마자 한 번 훑는다 -- 재시작 직후 놓친 신호를 한 주기 기다리지 않고 주워 담는다."""
    stop = Event()
    resume = _Resume(stop)

    WorkflowSweeper(resume, interval_seconds=0.0).run_until(stop)

    assert resume.sweeps == 2


def test_a_failed_sweep_is_logged_and_the_next_period_still_runs(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """안전망 스레드가 한 번의 DB 장애로 죽으면 그 뒤로는 조용히 아무도 구하지 않는다."""
    stop = Event()
    resume = _Resume(stop, fail_first=True)

    with caplog.at_level(logging.ERROR):
        WorkflowSweeper(resume, interval_seconds=0.0).run_until(stop)

    assert resume.sweeps == 2, "첫 실패 뒤에도 다음 주기가 돈다"
    assert any("sweep" in r.getMessage() for r in caplog.records if r.levelno >= logging.ERROR)
