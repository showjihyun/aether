"""spec 0002 2.4: Run 전이표 — 허용 전이만 통과하고, 종결 상태에서 나가는 전이는 0건.

`ALLOWED_PAIRS` 는 spec 2.4 의 표를 그대로 옮긴 것이지 구현의 내부 딕셔너리를 다시
읽은 것이 아닙니다 — 구현과 spec 이 갈라지면 이 테스트가 잡아야 하므로 오라클을
별도로 둡니다.
"""

from __future__ import annotations

import itertools

import pytest
from aether_runtime.domain.run import IllegalTransition, RunStatus, is_terminal, transition

# spec 0002 2.4 의 전이표 그대로.
ALLOWED_PAIRS: list[tuple[RunStatus, RunStatus]] = [
    (RunStatus.QUEUED, RunStatus.RUNNING),
    (RunStatus.QUEUED, RunStatus.CANCELLED),
    (RunStatus.RUNNING, RunStatus.WAITING),
    (RunStatus.WAITING, RunStatus.RUNNING),
    (RunStatus.RUNNING, RunStatus.SUCCEEDED),
    (RunStatus.WAITING, RunStatus.SUCCEEDED),
    (RunStatus.RUNNING, RunStatus.FAILED),
    (RunStatus.WAITING, RunStatus.FAILED),
    (RunStatus.RUNNING, RunStatus.CANCELLED),
    (RunStatus.WAITING, RunStatus.CANCELLED),
    (RunStatus.RUNNING, RunStatus.TIMED_OUT),
    (RunStatus.WAITING, RunStatus.TIMED_OUT),
]

TERMINAL_STATUSES = [
    RunStatus.SUCCEEDED,
    RunStatus.FAILED,
    RunStatus.CANCELLED,
    RunStatus.TIMED_OUT,
]

_ALL_PAIRS = list(itertools.product(RunStatus, RunStatus))
DISALLOWED_PAIRS = [pair for pair in _ALL_PAIRS if pair not in ALLOWED_PAIRS]


@pytest.mark.parametrize("current,target", ALLOWED_PAIRS)
def test_allowed_transition_returns_target(current: RunStatus, target: RunStatus) -> None:
    assert transition(current, target) is target


@pytest.mark.parametrize("current,target", DISALLOWED_PAIRS)
def test_disallowed_transition_raises_illegal_transition(
    current: RunStatus, target: RunStatus
) -> None:
    """종결 상태에서 나가는 전이(예: `succeeded -> running`)도 이 목록에 포함됩니다."""
    with pytest.raises(IllegalTransition):
        transition(current, target)


@pytest.mark.parametrize("status", TERMINAL_STATUSES)
def test_is_terminal_true_for_terminal_statuses(status: RunStatus) -> None:
    assert is_terminal(status) is True


@pytest.mark.parametrize("status", [RunStatus.QUEUED, RunStatus.RUNNING, RunStatus.WAITING])
def test_is_terminal_false_for_non_terminal_statuses(status: RunStatus) -> None:
    assert is_terminal(status) is False


def test_illegal_transition_carries_current_and_target() -> None:
    with pytest.raises(IllegalTransition) as excinfo:
        transition(RunStatus.SUCCEEDED, RunStatus.RUNNING)

    assert excinfo.value.current is RunStatus.SUCCEEDED
    assert excinfo.value.target is RunStatus.RUNNING
