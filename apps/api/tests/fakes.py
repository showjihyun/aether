"""spec 0001 2.9: `ApiKeyStore` 의 dict 기반 fake — 컨테이너 없는 유스케이스 테스트용.

`calls` 는 어떤 메서드가 어떤 인자로 불렸는지 순서대로 기록합니다.
`test_authenticate.py` 가 이것으로 "형식 불량 키는 store 를 조회하지 않는다"(spec 2.9,
열거 공격 표면 축소)를 증명합니다. 테스트 지원 코드이며 제품 코드가 아닙니다.

`clock` 은 `create`/`revoke` 가 시각을 얻는 유일한 통로입니다(spec 0002 R-11) — 테스트가
`datetime.now()` 와 실제 시간 경과 대신 주입한 시계를 전진시켜 "두 번째 revoke 가 첫
`revoked_at` 을 유지한다" 를 `sleep` 없이 결정적으로 증명할 수 있게 합니다
(`test_api_key_store_contract.py`).

`FakeRunDeclarationStore`·`FakeRunNotifier` 는 P1-5b(`RequestRun`·`GetRun`·`CancelRun`·
`ApplyRunStatus`)의 outbound 포트 fake 입니다(AR-9 — 유스케이스 테스트는 컨테이너
없이 돕니다, spec 0002 2.1, 2.2, 2.4, D-2, D-11).

`FakeRunEventReader` 는 P1-6(`ReadRunEvents`)의 outbound 포트(`RunEventReader`)
fake 입니다(spec 0002 2.7, D-4). `seed`로 미리 이벤트 열을 심고, `push`로 나중에
이벤트를 더할 수 있습니다 — 비어 있으면 `sleep` 대신 `asyncio.Event` 로 "새 이벤트가
생길 때까지" 기다립니다(R-11).

`FakeRequestTracing` 은 P1-8(`RequestTracing`)의 outbound 포트 fake 입니다(spec 0002
2.9, 2.18). 열린 span 의 이름·속성을 순서대로 기록하고, span 이 열려 있는 동안에만
고정된 `traceparent` 를 돌려줍니다(실제 OTel 어댑터가 span 밖에서 `None` 을 돌려주는
것과 같은 모양).
"""

from __future__ import annotations

import asyncio
import builtins
from collections.abc import AsyncIterator, Callable, Iterator, Mapping
from contextlib import contextmanager
from dataclasses import replace
from datetime import UTC, datetime
from uuid import UUID, uuid4

from aether_api.domain.agent import (
    Agent,
    AgentDetail,
    AgentNameTaken,
    AgentNotFound,
    AgentPage,
    AgentVersion,
    AgentVersionNotFound,
    AgentVersionSummary,
)
from aether_api.domain.api_key import ApiKey
from aether_api.domain.run import RunNotFound, RunView
from aether_runtime.domain.agent import AgentDefinition
from aether_runtime.domain.events import RunEvent
from aether_runtime.domain.failure import FailureReason
from aether_runtime.domain.run import RunStatus


def _default_clock() -> datetime:
    return datetime.now(UTC)


class FakeApiKeyStore:
    """`ApiKeyStore` 포트 계약의 인메모리 구현."""

    def __init__(self, clock: Callable[[], datetime] = _default_clock) -> None:
        self._by_id: dict[UUID, ApiKey] = {}
        self._id_by_hash: dict[str, UUID] = {}
        self.calls: list[tuple[str, str]] = []
        self._clock = clock

    def find_by_hash(self, key_hash: str) -> ApiKey | None:
        self.calls.append(("find_by_hash", key_hash))
        key_id = self._id_by_hash.get(key_hash)
        if key_id is None:
            return None
        return self._by_id[key_id]

    def create(self, label: str, key_hash: str) -> ApiKey:
        self.calls.append(("create", key_hash))
        if key_hash in self._id_by_hash:
            raise ValueError(f"duplicate key_hash: {key_hash!r}")
        key = ApiKey(
            id=uuid4(),
            label=label,
            key_hash=key_hash,
            created_at=self._clock(),
            revoked_at=None,
        )
        self._by_id[key.id] = key
        self._id_by_hash[key_hash] = key.id
        return key

    def revoke(self, key_id: UUID) -> None:
        """멱등: 이미 폐기된 키는 `revoked_at` 을 그대로 둡니다. 없는 id 는 `KeyError`."""
        self.calls.append(("revoke", str(key_id)))
        existing = self._by_id[key_id]  # 없으면 KeyError — 포트 계약(spec 2.9 H-3)
        if existing.revoked_at is None:
            self._by_id[key_id] = replace(existing, revoked_at=self._clock())

    # 테스트 준비 편의 — 포트 계약에는 없습니다.
    def seed(self, key: ApiKey) -> None:
        self._by_id[key.id] = key
        self._id_by_hash[key.key_hash] = key.id


class FakeAgentRepository:
    """`AgentRepository` 포트 계약(spec 0002 2.1 outbound)의 인메모리 구현.

    `add_version` 은 `current_version + 1` 로 순차 증가합니다(P1-1 usecase 테스트).
    커서(`list`)는 정렬된 목록의 정수 오프셋을 문자열로 감싼 것뿐입니다 — 불투명
    문자열이라는 계약만 지키면 되고, PostgreSQL 구현의 `(created_at, id)` 인코딩과
    같을 필요는 없습니다.
    """

    def __init__(self, clock: Callable[[], datetime] = _default_clock) -> None:
        self._agents: dict[UUID, Agent] = {}
        self._versions: dict[UUID, dict[int, AgentVersion]] = {}
        self._id_by_name: dict[str, UUID] = {}
        self._clock = clock

    def create(self, name: str, definition: AgentDefinition) -> Agent:
        if name in self._id_by_name:
            raise AgentNameTaken(name)
        agent_id = uuid4()
        now = self._clock()
        agent = Agent(id=agent_id, name=name, current_version=1, created_at=now, updated_at=now)
        self._agents[agent_id] = agent
        self._id_by_name[name] = agent_id
        self._versions[agent_id] = {
            1: AgentVersion(
                id=uuid4(), agent_id=agent_id, version=1, definition=definition, created_at=now
            )
        }
        return agent

    def get(self, agent_id: UUID) -> Agent:
        agent = self._agents.get(agent_id)
        if agent is None:
            raise AgentNotFound(agent_id)
        return agent

    def list(self, limit: int, cursor: str | None) -> AgentPage:
        ordered = sorted(self._agents.values(), key=lambda a: (a.created_at, str(a.id)))
        start = int(cursor) if cursor is not None else 0
        page_items = ordered[start : start + limit]
        end = start + len(page_items)
        next_cursor = str(end) if end < len(ordered) else None
        return AgentPage(items=page_items, next_cursor=next_cursor)

    def get_version(self, agent_id: UUID, version: int) -> AgentVersion:
        if agent_id not in self._agents:
            raise AgentNotFound(agent_id)
        found = self._versions[agent_id].get(version)
        if found is None:
            raise AgentVersionNotFound((agent_id, version))
        return found

    def list_versions(self, agent_id: UUID) -> builtins.list[AgentVersionSummary]:
        """`builtins.list` — 이 클래스의 `list` 메서드가 클래스 본문에서 내장 `list` 를 가립니다."""
        if agent_id not in self._agents:
            raise AgentNotFound(agent_id)
        versions = sorted(self._versions[agent_id].values(), key=lambda v: v.version)
        return [AgentVersionSummary(version=v.version, created_at=v.created_at) for v in versions]

    def add_version(self, agent_id: UUID, definition: AgentDefinition) -> AgentDetail:
        agent = self._agents.get(agent_id)
        if agent is None:
            raise AgentNotFound(agent_id)
        new_version_number = agent.current_version + 1
        now = self._clock()
        new_version = AgentVersion(
            id=uuid4(),
            agent_id=agent_id,
            version=new_version_number,
            definition=definition,
            created_at=now,
        )
        self._versions[agent_id][new_version_number] = new_version
        updated_agent = replace(agent, current_version=new_version_number, updated_at=now)
        self._agents[agent_id] = updated_agent
        versions = sorted(self._versions[agent_id].values(), key=lambda v: v.version)
        return AgentDetail(
            agent=updated_agent,
            definition=definition,
            versions=[
                AgentVersionSummary(version=v.version, created_at=v.created_at) for v in versions
            ],
        )


class FakeRunDeclarationStore:
    """`RunDeclarationStore` 포트 계약(spec 0002 2.1, 2.2, 2.4, D-2, D-11)의 인메모리 구현.

    `status_seq` 는 `RunView` 밖의 내부 부기입니다 — HTTP 응답에는 없는 값이지만
    `apply_status` 의 멱등 규칙(D-2)을 재현하려면 저장소가 마지막으로 적용한 `seq`
    를 기억해야 합니다.
    """

    def __init__(self, clock: Callable[[], datetime] = _default_clock) -> None:
        self._runs: dict[UUID, RunView] = {}
        self._status_seq: dict[UUID, int | None] = {}
        self._clock = clock

    def create(
        self,
        agent_id: UUID,
        agent_version_id: UUID,
        agent_version: int,
        input: str,
        requested_by: UUID,
    ) -> RunView:
        del agent_version_id  # 이 fake 는 HTTP 응답에 없는 FK 를 보관하지 않습니다.
        del input  # 저장하지 않습니다 — 이 fake 의 관찰 대상은 투영 열뿐입니다.
        run_id = uuid4()
        view = RunView(
            run_id=run_id,
            agent_id=agent_id,
            agent_version=agent_version,
            status=RunStatus.QUEUED,
            requested_at=self._clock(),
            requested_by=requested_by,
            started_at=None,
            finished_at=None,
            failure_reason=None,
            trace_id=None,
            cancel_requested_at=None,
        )
        self._runs[run_id] = view
        self._status_seq[run_id] = None
        return view

    def get(self, run_id: UUID) -> RunView | None:
        return self._runs.get(run_id)

    def request_cancel(self, run_id: UUID, at: datetime) -> RunView:
        view = self._runs.get(run_id)
        if view is None:
            raise RunNotFound(run_id)
        if view.cancel_requested_at is None:
            view = replace(view, cancel_requested_at=at)
            self._runs[run_id] = view
        return view

    def apply_status(
        self,
        run_id: UUID,
        *,
        seq: int,
        status: RunStatus,
        started_at: datetime | None,
        finished_at: datetime | None,
        failure_reason: FailureReason | None,
        trace_id: str | None,
    ) -> bool:
        view = self._runs.get(run_id)
        if view is None:
            return False
        current_seq = self._status_seq.get(run_id)
        if current_seq is not None and current_seq >= seq:
            return False
        self._status_seq[run_id] = seq
        self._runs[run_id] = replace(
            view,
            status=status,
            started_at=started_at if started_at is not None else view.started_at,
            finished_at=finished_at if finished_at is not None else view.finished_at,
            failure_reason=failure_reason if failure_reason is not None else view.failure_reason,
            trace_id=trace_id if trace_id is not None else view.trace_id,
        )
        return True


class FakeRunNotifier:
    """`RunNotifier` 포트의 인메모리 구현(spec 0002 2.2, 2.18). `should_fail` 이면
    `requested` 가 예외를 던집니다 — `RequestRunUseCase` 가 그 실패를 삼키고
    WARNING 을 남긴 뒤 정상 반환하는지(spec 2.2) 테스트가 증명합니다."""

    def __init__(self, *, should_fail: bool = False) -> None:
        self.calls: list[tuple[UUID, UUID, str | None]] = []
        self._should_fail = should_fail

    def requested(self, run_id: UUID, agent_version_id: UUID, traceparent: str | None) -> None:
        self.calls.append((run_id, agent_version_id, traceparent))
        if self._should_fail:
            raise RuntimeError("FakeRunNotifier: injected requested failure")


class FakeRunEventReader:
    """`RunEventReader` 포트의 인메모리 구현(spec 0002 2.7, D-4).

    `seed(run_id, events)` 로 미리 이벤트 열을 심습니다 — 심은 즉시 `stream_exists`
    가 `True` 를 돌려줍니다. `push(run_id, event)` 로 나중에 이벤트를 하나 더할 수
    있습니다(스트림이 아직 없다가 생기는 시나리오). `read()` 는 `after_seq` 보다 큰
    이벤트를 즉시 내고, 더 없으면 `sleep` 없이 `asyncio.Event` 로 다음 `push`/`seed`
    를 기다립니다 — `block_ms` 는 이 fake 에서 쓰지 않습니다(실제로 블록하지 않고
    이벤트로 깨어나기 때문).
    """

    def __init__(self) -> None:
        self._streams: dict[UUID, list[RunEvent]] = {}
        self._woken: dict[UUID, asyncio.Event] = {}

    def _event_for(self, run_id: UUID) -> asyncio.Event:
        woken = self._woken.get(run_id)
        if woken is None:
            woken = asyncio.Event()
            self._woken[run_id] = woken
        return woken

    def seed(self, run_id: UUID, events: list[RunEvent]) -> None:
        self._streams.setdefault(run_id, []).extend(events)
        self._event_for(run_id).set()

    def push(self, run_id: UUID, event: RunEvent) -> None:
        self._streams.setdefault(run_id, []).append(event)
        self._event_for(run_id).set()

    async def stream_exists(self, run_id: UUID) -> bool:
        return bool(self._streams.get(run_id))

    async def read(
        self, run_id: UUID, after_seq: int | None, block_ms: int
    ) -> AsyncIterator[RunEvent]:
        del block_ms  # 이 fake 는 실제로 블록하지 않고 Event 로 깨어납니다.
        last_seq = after_seq if after_seq is not None else 0
        while True:
            pending = [e for e in self._streams.get(run_id, []) if e.seq > last_seq]
            if pending:
                for event in pending:
                    yield event
                    last_seq = event.seq
                continue
            woken = self._event_for(run_id)
            woken.clear()
            await woken.wait()


_FAKE_TRACEPARENT = "00-" + "a" * 32 + "-" + "b" * 16 + "-01"


class FakeRequestTracing:
    """`RequestTracing` 포트의 인메모리 구현(spec 0002 2.9, 2.18, P1-8).

    `opened` 는 `span()` 이 열린 순서대로 `(name, attributes)` 쌍을 기록합니다.
    `current_traceparent()` 는 span 이 열려 있는 동안에만 고정 값을 돌려줍니다 —
    실제 OTel 어댑터가 활성 span 밖에서 `None` 을 돌려주는 것과 같은 모양입니다.
    """

    def __init__(self, *, traceparent: str = _FAKE_TRACEPARENT) -> None:
        self._traceparent = traceparent
        self._active = False
        self.opened: list[tuple[str, dict[str, str]]] = []

    @contextmanager
    def span(self, name: str, attributes: Mapping[str, str]) -> Iterator[None]:
        self.opened.append((name, dict(attributes)))
        previous = self._active
        self._active = True
        try:
            yield
        finally:
            self._active = previous

    def current_traceparent(self) -> str | None:
        return self._traceparent if self._active else None
