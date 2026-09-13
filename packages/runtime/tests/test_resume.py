"""spec 0002 2.4, D-10, R-15, R-16: 재개와 재발행.

(a) 종결 커밋 뒤 `StatusNotifier` 가 실패 — 두 번째 `ExecuteRun(run_id)` 호출이
    실패 없는 기준 실행과 **같은 `seq`** 로 `run.status`·`run.finished` 를 다시
    발행합니다(R-16). (b) `running` + lease 만료 — 저장된 `RunState` 에서 이어갑니다
    (처음부터 다시 시작하지 않습니다, R-15). (c) lease 유효 — `LeaseHeld`.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

import pytest
from aether_runtime.adapters.outbound.model_gateway.fake import FakeModelGateway
from aether_runtime.adapters.outbound.tools.registry import InMemoryToolRegistry
from aether_runtime.application.ports.outbound.model_gateway import ModelResponse
from aether_runtime.application.ports.outbound.run_declaration_reader import RunDeclaration
from aether_runtime.application.usecases.execute_run import ExecuteRunUseCase
from aether_runtime.domain.run import LeaseHeld, Message, RunState, RunStatus
from aether_runtime.domain.task import Task
from aether_runtime.domain.tools import ToolCall

from packages.runtime.tests.fakes import (
    FakeClock,
    FakeEventSink,
    FakeRunDeclarationReader,
    FakeRunStateStore,
    FakeStatusNotifier,
    InMemoryTracer,
)

_SYSTEM_PROMPT = "You are a helpful test agent."


def _definition(tools: list[str] | None = None) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "system_prompt": _SYSTEM_PROMPT,
        "model": {"id": "test-model"},
        "tools": tools or [],
        "policy": {
            "timeout_seconds": 120,
            "max_steps": 8,
            "model_retries": 0,
            "tool_retries": 0,
        },
    }


def _declare(run_input: str = "do the thing") -> tuple[UUID, UUID, FakeRunDeclarationReader]:
    run_id = uuid4()
    agent_version_id = uuid4()
    reader = FakeRunDeclarationReader(
        {run_id: RunDeclaration(run_id=run_id, agent_version_id=agent_version_id, input=run_input)},
        {agent_version_id: _definition()},
    )
    return run_id, agent_version_id, reader


def test_notifier_failure_after_terminal_commit_is_republished_with_same_seq() -> None:
    """spec 0002 R-16: 커밋(`set_status`+`save`) 뒤, 통지 실패로 죽었다고 가정합니다.
    두 번째 호출은 첫 시도가 실패 없이 끝났을 때와 **같은 `seq`** 로 `run.status`·
    `run.finished` 를 다시 발행하고 정상 반환합니다."""
    run_id, _, reader = _declare()
    clock = FakeClock()
    store = FakeRunStateStore(clock)
    baseline_events = FakeEventSink()
    baseline_notifier = FakeStatusNotifier()
    baseline_tracer = InMemoryTracer()
    baseline_gateway = FakeModelGateway([ModelResponse(text="ok", finish_reason="stop")])
    baseline = ExecuteRunUseCase(
        store=store,
        declarations=reader,
        gateway=baseline_gateway,
        tools=InMemoryToolRegistry(clock),
        events=baseline_events,
        notifier=baseline_notifier,
        tracer=baseline_tracer,
        clock=clock,
        owner="worker-baseline",
    )
    baseline_status = baseline(run_id)
    assert baseline_status == RunStatus.SUCCEEDED
    # 두 개의 `run.status` 이벤트(running, succeeded)가 나갑니다 — 종결(succeeded)
    # 을 나타내는 것은 마지막 항목입니다.
    baseline_status_seq = [e for e in baseline_events.published if e.type == "run.status"][-1].seq
    baseline_finished_seq = [e for e in baseline_events.published if e.type == "run.finished"][
        -1
    ].seq

    run_id_b, _, reader_b = _declare()
    clock_b = FakeClock()
    store_b = FakeRunStateStore(clock_b)
    events_b = FakeEventSink()
    notifier_b = FakeStatusNotifier(fail_after_successes=1)
    tracer_b = InMemoryTracer()
    gateway_b = FakeModelGateway([ModelResponse(text="ok", finish_reason="stop")])
    first_attempt = ExecuteRunUseCase(
        store=store_b,
        declarations=reader_b,
        gateway=gateway_b,
        tools=InMemoryToolRegistry(clock_b),
        events=events_b,
        notifier=notifier_b,
        tracer=tracer_b,
        clock=clock_b,
        owner="worker-a",
    )

    with pytest.raises(RuntimeError):
        first_attempt(run_id_b)

    # 커밋(status+state)은 끝났으므로 이미 종결로 관측됩니다. 종결을 알리는 마지막
    # `run.status`·`run.finished` 는 notify 실패로 아직 발행되지 못했습니다 — 그
    # 앞의 단계 이벤트(task.started 등)는 이미 나갔더라도 괜찮습니다(2.7 은 그
    # 이벤트들의 재발행을 요구하지 않습니다, 종결 알림만 R-16 의 대상입니다).
    assert store_b.status(run_id_b) == RunStatus.SUCCEEDED
    assert not any(e.type == "run.finished" for e in events_b.published)
    assert len(notifier_b.messages) == 1
    assert notifier_b.messages[0].status == RunStatus.RUNNING

    # 재시도하는 두 번째 worker 는 (새 연결이므로) 정상 동작하는 notifier 를 씁니다 —
    # 첫 시도의 실패는 그 시점의 일시적 오류였다는 전제입니다.
    notifier_b2 = FakeStatusNotifier()
    second_attempt = ExecuteRunUseCase(
        store=store_b,
        declarations=reader_b,
        gateway=gateway_b,
        tools=InMemoryToolRegistry(clock_b),
        events=events_b,
        notifier=notifier_b2,
        tracer=tracer_b,
        clock=clock_b,
        owner="worker-a",
    )

    resumed_status = second_attempt(run_id_b)

    assert resumed_status == RunStatus.SUCCEEDED
    # `events_b` 는 첫 시도의 단계 이벤트(running 전이 포함)를 이미 담고 있으므로,
    # 종결(succeeded) 을 나타내는 항목은 **마지막** `run.status`/`run.finished` 입니다.
    resumed_status_seq = [e for e in events_b.published if e.type == "run.status"][-1].seq
    resumed_finished_seq = [e for e in events_b.published if e.type == "run.finished"][-1].seq
    assert resumed_status_seq == baseline_status_seq
    assert resumed_finished_seq == baseline_finished_seq
    assert len(notifier_b2.messages) == 1
    assert notifier_b2.messages[0].status == RunStatus.SUCCEEDED
    assert notifier_b2.messages[0].seq == resumed_status_seq


def test_set_status_failure_after_state_saved_is_completed_and_republished_on_resume() -> None:
    """리뷰 B, spec 0002 R-16: 종결은 두 개의 커밋(`save(state)` 와 `set_status`) 으로
    이루어집니다. `save` 뒤 `set_status` 가 죽으면 `status()` 는 아직 비종결이지만
    `load()` 의 스냅숏은 이미 종결입니다 — 다음 호출은 그 스냅숏을 정본으로 커밋을
    마저 끝낸 뒤 같은 `seq` 로 재발행합니다. 이 경로는 lease 를 새로 잡지 않으므로
    다른 owner 로 재시도해도 `LeaseHeld` 가 나지 않습니다."""
    run_id, _, reader = _declare()
    clock = FakeClock()
    store = FakeRunStateStore(clock)
    events = FakeEventSink()
    notifier = FakeStatusNotifier()
    tracer = InMemoryTracer()
    gateway = FakeModelGateway([ModelResponse(text="ok", finish_reason="stop")])
    first_attempt = ExecuteRunUseCase(
        store=store,
        declarations=reader,
        gateway=gateway,
        tools=InMemoryToolRegistry(clock),
        events=events,
        notifier=notifier,
        tracer=tracer,
        clock=clock,
        owner="worker-a",
    )
    store.fail_next_terminal_set_status_once()

    with pytest.raises(RuntimeError):
        first_attempt(run_id)

    # 커밋의 절반(RunState 스냅숏)만 끝났습니다 -- status() 는 아직 비종결인데
    # load() 의 스냅숏은 이미 종결입니다.
    assert store.status(run_id) != RunStatus.SUCCEEDED
    loaded = store.load(run_id)
    assert loaded is not None
    assert loaded.status == RunStatus.SUCCEEDED
    expected_status_seq = loaded.last_seq - 1
    expected_finished_seq = loaded.last_seq

    second_attempt = ExecuteRunUseCase(
        store=store,
        declarations=reader,
        gateway=gateway,
        tools=InMemoryToolRegistry(clock),
        events=events,
        notifier=notifier,
        tracer=tracer,
        clock=clock,
        owner="worker-b",  # 다른 owner 여도 됩니다 -- 이 경로는 lease 를 잡지 않습니다.
    )

    resumed_status = second_attempt(run_id)

    assert resumed_status == RunStatus.SUCCEEDED
    assert store.status(run_id) == RunStatus.SUCCEEDED
    status_events = [e for e in events.published if e.type == "run.status"]
    finished_events = [e for e in events.published if e.type == "run.finished"]
    assert status_events[-1].seq == expected_status_seq
    assert finished_events[-1].seq == expected_finished_seq
    assert notifier.messages[-1].status == RunStatus.SUCCEEDED
    assert notifier.messages[-1].seq == expected_status_seq


def test_running_with_expired_lease_resumes_from_stored_state_instead_of_restarting() -> None:
    """spec 0002 2.4, R-15: `running` + lease 만료 → 저장된 `RunState` 에서 이어갑니다
    — step·메시지·`seq` 가 그대로 이어지고, system/user 메시지를 다시 만들지
    않습니다."""
    run_id, _, reader = _declare(run_input="원래 입력")
    clock = FakeClock()
    store = FakeRunStateStore(clock)

    # "죽은 worker" 가 남긴 lease 와 1단계까지 진행된 State 를 직접 심습니다.
    assert store.acquire_lease(run_id, owner="dead-worker", ttl_seconds=30) is True
    started_at = clock.now()
    store.set_status(run_id, RunStatus.RUNNING, started_at=started_at)
    prior_state = RunState(
        run_id=run_id,
        status=RunStatus.RUNNING,
        step=1,
        last_seq=6,
        started_at=started_at,
        messages=[
            Message(role="system", content=_SYSTEM_PROMPT),
            Message(role="user", content="원래 입력"),
            Message(role="assistant", content=""),
            Message(
                role="tool",
                tool_call_id="call_1",
                content="[observation tool=calculator trust=untrusted]2[/observation]",
            ),
        ],
        tasks=[
            Task(
                task_id="task-1",
                step=1,
                tool_calls=[
                    ToolCall(id="call_1", name="calculator", arguments={"expression": "1+1"})
                ],
            )
        ],
    )
    store.save(prior_state)

    clock.advance(31)  # lease_until(30초) 를 지나 새 worker 가 재획득할 수 있게 합니다.

    events = FakeEventSink()
    notifier = FakeStatusNotifier()
    tracer = InMemoryTracer()
    gateway = FakeModelGateway([ModelResponse(text="이어서 완료.", finish_reason="stop")])
    usecase = ExecuteRunUseCase(
        store=store,
        declarations=reader,
        gateway=gateway,
        tools=InMemoryToolRegistry(clock),
        events=events,
        notifier=notifier,
        tracer=tracer,
        clock=clock,
        owner="new-worker",
    )

    status = usecase(run_id)

    assert status == RunStatus.SUCCEEDED
    sent_messages = gateway.calls[0].messages
    assert sent_messages[0].content == _SYSTEM_PROMPT
    assert sent_messages[1].content == "원래 입력"
    assert sent_messages[-1].role == "tool"
    assert len(gateway.calls) == 1  # 재시작이었다면 이 시나리오는 도구 호출부터 다시 했을 것.
    published_seqs = [e.seq for e in events.published]
    assert published_seqs[0] == 7  # 저장된 last_seq(6) 다음부터 이어집니다 — 1 이 아님.


def test_running_with_valid_lease_raises_lease_held() -> None:
    """spec 0002 D-10, R-15: 유효한 lease 는 두 번째 실행자를 물러나게 합니다."""
    run_id, _, reader = _declare()
    clock = FakeClock()
    store = FakeRunStateStore(clock)
    assert store.acquire_lease(run_id, owner="alive-worker", ttl_seconds=60) is True
    store.set_status(run_id, RunStatus.RUNNING, started_at=clock.now())
    store.save(RunState(run_id=run_id, status=RunStatus.RUNNING, step=1, last_seq=3))

    usecase = ExecuteRunUseCase(
        store=store,
        declarations=reader,
        gateway=FakeModelGateway([]),
        tools=InMemoryToolRegistry(clock),
        events=FakeEventSink(),
        notifier=FakeStatusNotifier(),
        tracer=InMemoryTracer(),
        clock=clock,
        owner="other-worker",
    )

    with pytest.raises(LeaseHeld):
        usecase(run_id)
