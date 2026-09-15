"""spec 0002 2.16, R-11, 2.4, D-10, P1-4: 컨테이너 없는 테스트용 fake·인메모리 어댑터.

`FakeClock` 은 `Clock` 포트의 인메모리 구현입니다(spec 0002 R-4, R-11) — `sleep` 은
실제로 기다리지 않고 `advance()` 와 같은 일을 해 시계만 전진시킵니다. 테스트는 이
`advance()` 로 시간을 직접 통제해 lease 만료 같은 시간 의존 동작을 결정적으로
재현합니다.

`FakeRunStateStore` 는 `RunStateStore` 포트의 인메모리 구현입니다. `backend` 를
외부에서 공유하면(`FakeRunStateStore.new_backend()`) 서로 다른 `FakeRunStateStore`
인스턴스가 같은 저장소를 보게 되어, PostgreSQL 어댑터가 연결마다 새로 열려도 같은
DB 를 보는 것과 같은 모양으로 "새 store 인스턴스가 같은 RunState 를 load" 계약을
검증할 수 있습니다(mvp-backlog P1-2b 완료 판정).

`FakeEventSink`·`FakeStatusNotifier`·`FakeRunDeclarationReader`·`InMemoryTracer`·
`FakeTool`·`FakeToolRegistry` 는 P1-4(`ExecuteRun`)의 outbound 포트 fake 입니다(AR-9 —
유스케이스 테스트는 컨테이너 없이 돕니다).

`FakeLeaseKeeper` 는 `LeaseKeeper` 포트의 결정적 fake 입니다(spec 0002 C-13, P1-7) —
몇 번째 `keep()` 호출에서 lease 를 잃는지를 `lost_on_keep` 으로 미리 정해 둘 수
있습니다(실제 스레드를 띄우지 않습니다 — 프로덕션 스레드 타이밍은
`test_threaded_lease_keeper.py` 가 따로 검증합니다).

테스트 지원 코드이며 제품 코드가 아닙니다.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from aether_runtime.application.ports.outbound.run_declaration_reader import RunDeclaration
from aether_runtime.application.ports.outbound.status_notifier import StatusMessage
from aether_runtime.domain.events import RunEvent
from aether_runtime.domain.failure import FailureReason
from aether_runtime.domain.run import RunState, RunStatus
from aether_runtime.domain.tools import ToolResult


class FakeClock:
    """`Clock` 포트의 결정적 구현(spec 0002 R-11) — `sleep` 은 시계만 전진시킵니다.

    `sleep_calls` 는 `sleep()` 으로 들어온 인자만 기록합니다(`advance()` 로 직접
    시간을 조작하는 테스트 코드와 구분하기 위해서입니다) — P1-7 의 재시도 백오프가
    실제로 `Clock.sleep` 을 부른 지연 값 열을 단언할 때 씁니다(spec 0002 2.8)."""

    def __init__(self, start: datetime | None = None) -> None:
        self._now = start if start is not None else datetime(2026, 1, 1, tzinfo=UTC)
        self._monotonic = 0.0
        self.sleep_calls: list[float] = []

    def now(self) -> datetime:
        return self._now

    def monotonic(self) -> float:
        return self._monotonic

    def sleep(self, seconds: float) -> None:
        self.sleep_calls.append(seconds)
        self.advance(seconds)

    def advance(self, seconds: float) -> None:
        """실제로 기다리지 않고 시계를 `seconds` 만큼 전진시킵니다."""
        self._now = self._now + timedelta(seconds=seconds)
        self._monotonic += seconds


@dataclass
class _Backend:
    """`FakeRunStateStore` 여러 인스턴스가 공유할 수 있는 저장소 본체."""

    states: dict[UUID, RunState] = field(default_factory=dict)
    status: dict[UUID, RunStatus] = field(default_factory=dict)
    failure_reason: dict[UUID, FailureReason | None] = field(default_factory=dict)
    trace_id: dict[UUID, str | None] = field(default_factory=dict)
    lease_owner: dict[UUID, str | None] = field(default_factory=dict)
    lease_until: dict[UUID, datetime | None] = field(default_factory=dict)
    started_at: dict[UUID, datetime | None] = field(default_factory=dict)
    finished_at: dict[UUID, datetime | None] = field(default_factory=dict)


class FakeRunStateStore:
    """`RunStateStore` 포트의 인메모리 구현(spec 0002 2.1, 2.4, 2.10, D-10)."""

    def __init__(self, clock: FakeClock, *, backend: _Backend | None = None) -> None:
        self._clock = clock
        self._backend = backend if backend is not None else _Backend()
        self._fail_next_terminal_set_status = False

    def fail_next_terminal_set_status_once(self) -> None:
        """`finished_at` 이 있는(=`_finalize` 가 종결 때만 부르는) 다음 `set_status`
        호출 딱 한 번만 예외를 냅니다 — 리뷰 B: `save(state)` 커밋 뒤 `set_status` 가
        죽는 crash 창을 재현합니다. 중간 전이(`_announce`, `finished_at` 없음)는
        건드리지 않으므로 몇 단계를 거치든 정확히 종결 호출만 실패합니다. 한 번
        실패한 뒤로는 정상 동작합니다(같은 store 인스턴스로 재시도를 표현하기 위해)."""
        self._fail_next_terminal_set_status = True

    @staticmethod
    def new_backend() -> _Backend:
        """여러 `FakeRunStateStore` 인스턴스가 공유할 빈 저장소를 만듭니다."""
        return _Backend()

    def load(self, run_id: UUID) -> RunState | None:
        state = self._backend.states.get(run_id)
        return state.model_copy(deep=True) if state is not None else None

    def save(self, state: RunState) -> None:
        self._backend.states[state.run_id] = state.model_copy(deep=True)

    def _ensure_execution_row(self, run_id: UUID) -> None:
        if run_id not in self._backend.status:
            self._backend.status[run_id] = RunStatus.QUEUED
            self._backend.failure_reason[run_id] = None
            self._backend.trace_id[run_id] = None
            self._backend.lease_owner[run_id] = None
            self._backend.lease_until[run_id] = None
            self._backend.started_at[run_id] = None
            self._backend.finished_at[run_id] = None

    def acquire_lease(self, run_id: UUID, owner: str, ttl_seconds: float) -> bool:
        self._ensure_execution_row(run_id)
        until = self._backend.lease_until.get(run_id)
        now = self._clock.now()
        if until is not None and until >= now:
            return False
        self._backend.lease_owner[run_id] = owner
        self._backend.lease_until[run_id] = now + timedelta(seconds=ttl_seconds)
        return True

    def renew_lease(self, run_id: UUID, owner: str, ttl_seconds: float) -> bool:
        if self._backend.lease_owner.get(run_id) != owner:
            return False
        self._backend.lease_until[run_id] = self._clock.now() + timedelta(seconds=ttl_seconds)
        return True

    def release(self, run_id: UUID, owner: str) -> None:
        if self._backend.lease_owner.get(run_id) == owner:
            self._backend.lease_owner[run_id] = None
            self._backend.lease_until[run_id] = None

    def status(self, run_id: UUID) -> RunStatus | None:
        return self._backend.status.get(run_id)

    def set_status(
        self,
        run_id: UUID,
        status: RunStatus,
        *,
        failure_reason: FailureReason | None = None,
        trace_id: str | None = None,
        started_at: datetime | None = None,
        finished_at: datetime | None = None,
    ) -> None:
        if self._fail_next_terminal_set_status and finished_at is not None:
            self._fail_next_terminal_set_status = False
            raise RuntimeError("FakeRunStateStore: injected set_status failure")
        self._ensure_execution_row(run_id)
        self._backend.status[run_id] = status
        if failure_reason is not None:
            self._backend.failure_reason[run_id] = failure_reason
        if trace_id is not None:
            self._backend.trace_id[run_id] = trace_id
        if started_at is not None:
            self._backend.started_at[run_id] = started_at
        if finished_at is not None:
            self._backend.finished_at[run_id] = finished_at

    def started_at(self, run_id: UUID) -> datetime | None:
        """Protocol 밖의 테스트 전용 조회 — PostgreSQL 쪽은 `data.run_executions` 를
        직접 SELECT 합니다(`test_run_state_store_contract.py`)."""
        return self._backend.started_at.get(run_id)

    def finished_at(self, run_id: UUID) -> datetime | None:
        return self._backend.finished_at.get(run_id)


class FakeEventSink:
    """`EventSink` 포트의 인메모리 구현(spec 0002 2.7 개정 2).

    Redis 의 "top ID 이하 explicit XADD 거부" 를 모사하지 않습니다 — 계약이 **같은
    `seq` 재발행은 성공**으로 정했기 때문입니다(plan 0002 P1-4 순서 1). `fail_first_n`
    은 R-16(재발행) 테스트가 "종결 커밋 뒤 발행 실패" 를 주입할 때 씁니다.
    """

    def __init__(self, *, fail_first_n: int = 0) -> None:
        self.published: list[RunEvent] = []
        self._fail_remaining = fail_first_n

    def publish(self, event: RunEvent) -> None:
        if self._fail_remaining > 0:
            self._fail_remaining -= 1
            raise RuntimeError("FakeEventSink: injected publish failure")
        self.published.append(event)


class FakeStatusNotifier:
    """`StatusNotifier` 포트의 인메모리 구현(spec 0002 2.18).

    `fail_after_successes` 는 R-16 재발행 테스트가 "종결 커밋 뒤 notify 실패" 를
    주입할 때 씁니다 — 그 값만큼 성공한 뒤부터는 이후 호출이 전부 실패합니다(예:
    `1` 이면 첫 번째 `notify` 는 성공하고, 종결 전이의 두 번째 `notify` 부터
    실패합니다). `None`(기본)이면 실패하지 않습니다.
    """

    def __init__(self, *, fail_after_successes: int | None = None) -> None:
        self.messages: list[StatusMessage] = []
        self._fail_after = fail_after_successes

    def notify(self, message: StatusMessage) -> None:
        if self._fail_after is not None and len(self.messages) >= self._fail_after:
            raise RuntimeError("FakeStatusNotifier: injected notify failure")
        self.messages.append(message)


class FakeRunDeclarationReader:
    """`RunDeclarationReader` 포트의 인메모리 구현(spec 0002 D-11).

    `set_cancel_requested` 는 테스트가 루프 도중(단계 사이) 취소를 관측시키기 위한
    편의 메서드입니다 — 취소의 정본은 `cancel_requested_at` 하나뿐이므로(D-11) 이
    메서드가 그 값을 바꾸는 유일한 통로입니다.
    """

    def __init__(
        self,
        declarations: dict[UUID, RunDeclaration],
        definitions: dict[UUID, dict[str, Any]],
    ) -> None:
        self._declarations = declarations
        self._definitions = definitions

    def declaration(self, run_id: UUID) -> RunDeclaration | None:
        return self._declarations.get(run_id)

    def definition(self, agent_version_id: UUID) -> dict[str, Any]:
        return self._definitions[agent_version_id]

    def set_cancel_requested(self, run_id: UUID, at: datetime) -> None:
        current = self._declarations[run_id]
        self._declarations[run_id] = current.model_copy(update={"cancel_requested_at": at})


@dataclass
class SpanRecord:
    """`InMemoryTracer` 가 기록한 span 하나 — 부모 이름과 속성을 그대로 보관합니다."""

    name: str
    attributes: dict[str, str]
    parent: str | None


class InMemoryTracer:
    """`Tracer` 포트의 인메모리 구현(spec 0002 2.9, R-5) — span 부모–자식과 속성을
    기록합니다. `current_trace_id()` 는 생성 시 고정한 값을 돌려줍니다."""

    def __init__(self, trace_id: str = "trace-fake") -> None:
        self._trace_id = trace_id
        self.spans: list[SpanRecord] = []
        self._stack: list[SpanRecord] = []

    def current_trace_id(self) -> str | None:
        return self._trace_id

    @contextmanager
    def span(self, name: str, attributes: Mapping[str, str]) -> Iterator[None]:
        parent = self._stack[-1].name if self._stack else None
        record = SpanRecord(name=name, attributes=dict(attributes), parent=parent)
        self.spans.append(record)
        self._stack.append(record)
        try:
            yield
        finally:
            self._stack.pop()


@dataclass
class FakeTool:
    """`Tool` 포트를 만족하는 결정적 테스트 도구 — 정확한 도구 파싱(계산기 등)은
    `test_tools.py` 가 따로 증명하므로, 루프 테스트는 이 fake 로 도구 내용과 무관하게
    호출·결과·`is_error`·긴 응답(잘림 테스트)만 통제합니다."""

    name: str
    description: str = "fake tool"
    input_schema: dict[str, Any] = field(default_factory=dict)
    result: ToolResult = field(default_factory=lambda: ToolResult(content="ok"))
    raises: Exception | None = None
    calls: list[dict[str, Any]] = field(default_factory=list)

    def run(self, arguments: dict[str, Any]) -> ToolResult:
        self.calls.append(dict(arguments))
        if self.raises is not None:
            raise self.raises
        return self.result


class FakeToolRegistry:
    """`ToolRegistry` 포트의 인메모리 구현 — `get` 은 없는 이름에 `KeyError`."""

    def __init__(self, tools: Mapping[str, FakeTool]) -> None:
        self._tools = dict(tools)

    def get(self, name: str) -> FakeTool:
        return self._tools[name]

    def names(self) -> frozenset[str]:
        return frozenset(self._tools)


@dataclass
class _FakeLeaseStatus:
    """`LeaseStatus` 포트를 만족하는 값 객체 — `keep()` 호출 시점에 결정되어 그 뒤로
    바뀌지 않습니다(실제 스레드가 없으므로 갱신 도중 값이 바뀔 일도 없습니다)."""

    lost: bool = False


class FakeLeaseKeeper:
    """`LeaseKeeper` 포트의 결정적 fake(spec 0002 C-13) — `lost_on_keep` 번째
    (1부터) `keep()` 호출에서 `lost=True` 를 돌려줍니다. `None`(기본)이면 절대
    잃지 않습니다. 실제 스레드를 띄우지 않으므로 `Clock.sleep` 처럼 결정적입니다."""

    def __init__(self, *, lost_on_keep: int | None = None) -> None:
        self._lost_on_keep = lost_on_keep
        self._keep_count = 0
        self.calls: list[tuple[UUID, str, float]] = []

    @contextmanager
    def keep(self, run_id: UUID, owner: str, ttl_seconds: float) -> Iterator[_FakeLeaseStatus]:
        self._keep_count += 1
        self.calls.append((run_id, owner, ttl_seconds))
        lost = self._lost_on_keep is not None and self._keep_count == self._lost_on_keep
        yield _FakeLeaseStatus(lost=lost)
