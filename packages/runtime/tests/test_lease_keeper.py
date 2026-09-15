"""spec 0002 C-13, D-10 (P1-7): `ExecuteRunUseCase` 가 모델·도구 호출을
`LeaseKeeper.keep(...)` 로 감싸고, 그 호출 중 lease 를 잃으면(`lost=True`) 결과를
버리고 `LeaseHeld` 로 물러납니다 — 그 단계의 `RunState` 저장·lease `release`·
`run.finished` 발행이 전부 0회여야 합니다(다른 worker 가 이미 이 Run 을 가져갔을 수
있으므로 쓰지 않습니다, R-16 의 재발행이 새 소유자 쪽에서 이어받습니다).

단계 끝의 평범한 `renew_lease` 가 `False` 를 돌려주는 경우도 같은 결과입니다 —
`LeaseKeeper` 를 거치지 않는 경로지만 같은 원칙(저장 전 `LeaseHeld`)이 적용됩니다.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

import pytest
from aether_runtime.adapters.outbound.model_gateway.fake import FakeModelGateway
from aether_runtime.adapters.outbound.tools.registry import InMemoryToolRegistry
from aether_runtime.application.ports.outbound.model_gateway import ModelResponse
from aether_runtime.application.ports.outbound.run_declaration_reader import RunDeclaration
from aether_runtime.application.ports.outbound.run_state_store import RunStateStore
from aether_runtime.application.usecases.execute_run import ExecuteRunUseCase
from aether_runtime.domain.failure import FailureReason
from aether_runtime.domain.run import LeaseHeld, RunState, RunStatus
from aether_runtime.domain.tools import ToolCall

from packages.runtime.tests.fakes import (
    FakeClock,
    FakeEventSink,
    FakeLeaseKeeper,
    FakeRunDeclarationReader,
    FakeRunStateStore,
    FakeStatusNotifier,
    InMemoryTracer,
)

_OWNER = "worker-test"


def _definition(tools: list[str] | None = None) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "system_prompt": "You are a helpful test agent.",
        "model": {"id": "test-model"},
        "tools": tools or [],
        "policy": {
            "timeout_seconds": 120,
            "max_steps": 8,
            "model_retries": 0,
            "tool_retries": 0,
        },
    }


def _declare(
    definition: dict[str, Any] | None = None,
) -> tuple[UUID, FakeRunDeclarationReader]:
    run_id = uuid4()
    agent_version_id = uuid4()
    reader = FakeRunDeclarationReader(
        {run_id: RunDeclaration(run_id=run_id, agent_version_id=agent_version_id, input="hi")},
        {agent_version_id: definition if definition is not None else _definition()},
    )
    return run_id, reader


def test_lease_lost_during_model_call_raises_lease_held_without_committing() -> None:
    """spec 0002 C-13: 모델 호출 중 `lost=True` → `LeaseHeld`, 그 단계의 `RunState`
    저장 0회·release 0회·`run.finished` 발행 0회."""
    run_id, reader = _declare()
    clock = FakeClock()
    store = FakeRunStateStore(clock)
    events = FakeEventSink()
    notifier = FakeStatusNotifier()
    tracer = InMemoryTracer()
    gateway = FakeModelGateway([ModelResponse(text="hi there", finish_reason="stop")])
    lease_keeper = FakeLeaseKeeper(lost_on_keep=1)

    usecase = ExecuteRunUseCase(
        store,
        reader,
        gateway,
        InMemoryToolRegistry(clock),
        events,
        notifier,
        tracer,
        clock,
        owner=_OWNER,
        lease_keeper=lease_keeper,
    )

    with pytest.raises(LeaseHeld):
        usecase(run_id)

    assert store.load(run_id) is None, "lease 를 잃은 단계의 RunState 는 저장되지 않습니다"
    assert not any(e.type == "run.finished" for e in events.published)
    # release 가 불리지 않았다면 다른 owner 는 아직 lease 를 잡지 못합니다(만료 전).
    assert store.acquire_lease(run_id, owner="other-worker", ttl_seconds=60) is False


def test_lease_lost_during_tool_call_raises_lease_held_without_committing() -> None:
    """spec 0002 C-13: 도구 호출 중 `lost=True` 여도 같은 결과입니다."""
    run_id, reader = _declare(definition=_definition(tools=["calculator"]))
    clock = FakeClock()
    store = FakeRunStateStore(clock)
    events = FakeEventSink()
    notifier = FakeStatusNotifier()
    tracer = InMemoryTracer()
    gateway = FakeModelGateway(
        [
            ModelResponse(
                tool_calls=[
                    ToolCall(id="call_1", name="calculator", arguments={"expression": "1+1"})
                ],
                finish_reason="tool_calls",
            ),
            ModelResponse(text="2 입니다.", finish_reason="stop"),
        ]
    )
    # keep() 호출 순서: 1) 모델 호출(성공, lost 아님) 2) 도구 호출(lost).
    lease_keeper = FakeLeaseKeeper(lost_on_keep=2)

    usecase = ExecuteRunUseCase(
        store,
        reader,
        gateway,
        InMemoryToolRegistry(clock),
        events,
        notifier,
        tracer,
        clock,
        owner=_OWNER,
        lease_keeper=lease_keeper,
    )

    with pytest.raises(LeaseHeld):
        usecase(run_id)

    assert store.load(run_id) is None
    assert not any(e.type == "run.finished" for e in events.published)
    assert store.acquire_lease(run_id, owner="other-worker", ttl_seconds=60) is False


class _RenewFailsAlwaysStore:
    """`RunStateStore` 포트를 감싸 `renew_lease` 만 항상 `False` 로 강제합니다 — 단계
    끝의 평범한 `renew_lease` 실패 경로(저장 전 `LeaseHeld`)를 결정적으로 재현합니다."""

    def __init__(self, inner: FakeRunStateStore) -> None:
        self._inner = inner
        self.renew_calls = 0

    def load(self, run_id: UUID) -> RunState | None:
        return self._inner.load(run_id)

    def save(self, state: RunState) -> None:
        self._inner.save(state)

    def acquire_lease(self, run_id: UUID, owner: str, ttl_seconds: float) -> bool:
        return self._inner.acquire_lease(run_id, owner, ttl_seconds)

    def renew_lease(self, run_id: UUID, owner: str, ttl_seconds: float) -> bool:
        self.renew_calls += 1
        return False

    def release(self, run_id: UUID, owner: str) -> None:
        self._inner.release(run_id, owner)

    def status(self, run_id: UUID) -> RunStatus | None:
        return self._inner.status(run_id)

    def set_status(
        self,
        run_id: UUID,
        status: RunStatus,
        *,
        failure_reason: FailureReason | None = None,
        trace_id: str | None = None,
        started_at: Any = None,
        finished_at: Any = None,
    ) -> None:
        self._inner.set_status(
            run_id,
            status,
            failure_reason=failure_reason,
            trace_id=trace_id,
            started_at=started_at,
            finished_at=finished_at,
        )


def test_renew_lease_returning_false_at_step_end_raises_lease_held_before_saving() -> None:
    """spec 0002 C-13, D-10: 계속되는 단계 끝의 평범한 `renew_lease` 가 `False`
    여도 lease 를 잃은 것과 같은 결과 — 저장 전 `LeaseHeld`."""
    inner = FakeRunStateStore(FakeClock())
    run_id, reader = _declare(definition=_definition(tools=["calculator"]))
    store: RunStateStore = _RenewFailsAlwaysStore(inner)
    clock = FakeClock()
    events = FakeEventSink()
    notifier = FakeStatusNotifier()
    tracer = InMemoryTracer()
    gateway = FakeModelGateway(
        [
            ModelResponse(
                tool_calls=[
                    ToolCall(id="call_1", name="calculator", arguments={"expression": "1+1"})
                ],
                finish_reason="tool_calls",
            ),
            ModelResponse(text="2 입니다.", finish_reason="stop"),
        ]
    )

    usecase = ExecuteRunUseCase(
        store,
        reader,
        gateway,
        InMemoryToolRegistry(clock),
        events,
        notifier,
        tracer,
        clock,
        owner=_OWNER,
    )

    with pytest.raises(LeaseHeld):
        usecase(run_id)

    assert inner.load(run_id) is None, "저장 전에 LeaseHeld 가 나야 합니다"
    assert not any(e.type == "run.finished" for e in events.published)


def test_lease_not_lost_behaves_as_before() -> None:
    """spec 0002 C-13: `FakeLeaseKeeper` 가 절대 잃지 않으면(`lost_on_keep=None`)
    기존과 같이 `succeeded` 로 끝납니다."""
    run_id, reader = _declare()
    clock = FakeClock()
    store = FakeRunStateStore(clock)
    events = FakeEventSink()
    notifier = FakeStatusNotifier()
    tracer = InMemoryTracer()
    gateway = FakeModelGateway([ModelResponse(text="hi there", finish_reason="stop")])
    lease_keeper = FakeLeaseKeeper()

    usecase = ExecuteRunUseCase(
        store,
        reader,
        gateway,
        InMemoryToolRegistry(clock),
        events,
        notifier,
        tracer,
        clock,
        owner=_OWNER,
        lease_keeper=lease_keeper,
    )

    status = usecase(run_id)

    assert status == RunStatus.SUCCEEDED
    assert store.status(run_id) == RunStatus.SUCCEEDED
    assert lease_keeper.calls  # keep() 이 실제로 불렸습니다(모델 호출을 감쌉니다)
