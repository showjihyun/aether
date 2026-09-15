"""spec 0002 2.2, 2.4, D-9: `RequestRunUseCase` — 버전 결정 → 선언(커밋) → 통지.

`FakeAgentRepository`·`FakeRunDeclarationStore`·`FakeRunNotifier` 하나로 컨테이너
없이 돕니다(architecture.md 3.1 "TDD" 이득). 통지 실패는 `RequestRunUseCase` 가
삼키고 WARNING 을 남긴 뒤에도 `202` 로 이어질 값(정상 `RunView`)을 그대로 돌려줍니다
(spec 2.2 — 커밋 뒤 XADD, XADD 실패는 WARNING).
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

import pytest
from aether_api.application.usecases.create_agent import CreateAgentUseCase
from aether_api.application.usecases.request_run import RequestRunUseCase
from aether_api.domain.agent import AgentNotFound, AgentVersionNotFound
from aether_runtime.domain.agent import AgentDefinition
from aether_runtime.domain.run import RunStatus

from apps.api.tests.fakes import (
    FakeAgentRepository,
    FakeRequestTracing,
    FakeRunDeclarationStore,
    FakeRunNotifier,
)


def _definition(**overrides: Any) -> AgentDefinition:
    payload: dict[str, Any] = {"schema_version": 1, "system_prompt": "You are a helper."}
    payload.update(overrides)
    return AgentDefinition.model_validate(payload)


def _make_agent(repo: FakeAgentRepository) -> Any:
    create_agent = CreateAgentUseCase(repo)
    return create_agent("weather-bot", _definition())


def test_request_run_defaults_to_current_version_and_records_requested_by() -> None:
    repo = FakeAgentRepository()
    agent = _make_agent(repo)
    store = FakeRunDeclarationStore()
    notifier = FakeRunNotifier()
    request_run = RequestRunUseCase(repo, store, notifier)
    requester = uuid4()

    view = request_run(agent.id, "do the thing", None, requester)

    assert view.agent_id == agent.id
    assert view.agent_version == 1
    assert view.status == RunStatus.QUEUED
    assert view.requested_by == requester


def test_request_run_with_explicit_agent_version() -> None:
    repo = FakeAgentRepository()
    agent = _make_agent(repo)
    store = FakeRunDeclarationStore()
    notifier = FakeRunNotifier()
    request_run = RequestRunUseCase(repo, store, notifier)

    view = request_run(agent.id, "do the thing", 1, uuid4())

    assert view.agent_version == 1


def test_request_run_unknown_agent_raises_agent_not_found() -> None:
    repo = FakeAgentRepository()
    store = FakeRunDeclarationStore()
    notifier = FakeRunNotifier()
    request_run = RequestRunUseCase(repo, store, notifier)

    with pytest.raises(AgentNotFound):
        request_run(uuid4(), "x", None, uuid4())


def test_request_run_unknown_version_raises_agent_version_not_found() -> None:
    repo = FakeAgentRepository()
    agent = _make_agent(repo)
    store = FakeRunDeclarationStore()
    notifier = FakeRunNotifier()
    request_run = RequestRunUseCase(repo, store, notifier)

    with pytest.raises(AgentVersionNotFound):
        request_run(agent.id, "x", 2, uuid4())


def test_request_run_notifies_after_declaration_is_created() -> None:
    """spec 2.2: 통지는 선언이 만들어진(커밋된) `run_id` 로 정확히 한 번 이루어집니다."""
    repo = FakeAgentRepository()
    agent = _make_agent(repo)
    store = FakeRunDeclarationStore()
    notifier = FakeRunNotifier()
    request_run = RequestRunUseCase(repo, store, notifier)

    view = request_run(agent.id, "do the thing", None, uuid4())

    assert len(notifier.calls) == 1
    notified_run_id, _agent_version_id, _traceparent = notifier.calls[0]
    assert notified_run_id == view.run_id
    # 통지 시점에 store 는 이미 그 run_id 를 알고 있습니다(커밋 뒤 통지).
    assert store.get(view.run_id) is not None


def test_request_run_returns_normally_when_notifier_fails(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """spec 2.2: XADD 실패는 202 를 막지 않고 WARNING 만 남깁니다."""
    repo = FakeAgentRepository()
    agent = _make_agent(repo)
    store = FakeRunDeclarationStore()
    notifier = FakeRunNotifier(should_fail=True)
    request_run = RequestRunUseCase(repo, store, notifier)

    with caplog.at_level("WARNING"):
        view = request_run(agent.id, "do the thing", None, uuid4())

    assert view.status == RunStatus.QUEUED
    assert store.get(view.run_id) is not None
    assert any(record.levelname == "WARNING" for record in caplog.records)


def test_request_run_without_tracing_sends_none_traceparent() -> None:
    """spec 0002 2.18: `tracing` 을 생략하면(기존 호출) 내부 no-op 을 써서
    `traceparent=None` 그대로 통지합니다 — 기존 호출부(어댑터 조립)를 바꾸지 않아도
    이 유스케이스는 그대로 동작합니다."""
    repo = FakeAgentRepository()
    agent = _make_agent(repo)
    store = FakeRunDeclarationStore()
    notifier = FakeRunNotifier()
    request_run = RequestRunUseCase(repo, store, notifier)

    request_run(agent.id, "do the thing", None, uuid4())

    _run_id, _agent_version_id, traceparent = notifier.calls[0]
    assert traceparent is None


def test_request_run_opens_run_request_span_and_forwards_its_traceparent() -> None:
    """spec 0002 2.9, 2.18: `tracing` 이 있으면 `run.request` span 안에서 선언·통지가
    이루어지고, 통지에는 그 span 이 낸 `traceparent` 가 실립니다."""
    repo = FakeAgentRepository()
    agent = _make_agent(repo)
    version = repo.get_version(agent.id, 1)
    store = FakeRunDeclarationStore()
    notifier = FakeRunNotifier()
    fixed_traceparent = "00-" + "1" * 32 + "-" + "2" * 16 + "-01"
    tracing = FakeRequestTracing(traceparent=fixed_traceparent)
    request_run = RequestRunUseCase(repo, store, notifier, tracing=tracing)

    view = request_run(agent.id, "do the thing", None, uuid4())

    assert tracing.opened == [
        (
            "run.request",
            {"aether.agent_id": str(agent.id), "aether.agent_version_id": str(version.id)},
        )
    ]
    notified_run_id, notified_version_id, notified_traceparent = notifier.calls[0]
    assert notified_run_id == view.run_id
    assert notified_version_id == version.id
    assert notified_traceparent == fixed_traceparent
