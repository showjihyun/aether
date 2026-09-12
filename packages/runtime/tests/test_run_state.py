"""spec 0002 2.1: `RunState` 직렬화 왕복과 필드 불변식(`step`·`last_seq` 는 음수 불가 —
`seq` 는 Run 안에서 1 부터 단조 증가하므로(2.7) 음수는 정의역 밖입니다).
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from aether_runtime.domain.run import Message, RunState, RunStatus
from aether_runtime.domain.task import Task
from aether_runtime.domain.tools import ToolCall
from pydantic import ValidationError


def test_run_state_round_trips_through_json() -> None:
    state = RunState(
        run_id=uuid4(),
        messages=[
            Message(role="system", content="You are helpful."),
            Message(role="user", content="hi"),
        ],
        step=2,
        tasks=[],
        last_seq=5,
        status=RunStatus.RUNNING,
    )

    restored = RunState.model_validate_json(state.model_dump_json())

    assert restored == state


def test_run_state_round_trips_with_tasks_and_tool_calls() -> None:
    state = RunState(
        run_id=uuid4(),
        status=RunStatus.WAITING,
        step=1,
        last_seq=1,
        tasks=[
            Task(
                task_id="t1",
                step=1,
                tool_calls=[ToolCall(id="call_1", name="clock", arguments={})],
            )
        ],
    )

    restored = RunState.model_validate_json(state.model_dump_json())

    assert restored == state


def test_run_state_defaults_are_empty_and_zero() -> None:
    state = RunState(run_id=uuid4(), status=RunStatus.QUEUED)

    assert state.messages == []
    assert state.tasks == []
    assert state.step == 0
    assert state.last_seq == 0


def test_run_state_rejects_negative_last_seq() -> None:
    with pytest.raises(ValidationError):
        RunState(run_id=uuid4(), status=RunStatus.QUEUED, last_seq=-1)


def test_run_state_rejects_negative_step() -> None:
    with pytest.raises(ValidationError):
        RunState(run_id=uuid4(), status=RunStatus.QUEUED, step=-1)
