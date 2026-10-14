"""spec 0005 2.5 개정 3 (P4-2a B1): `DeclareWorkflowAgentRunUseCase` — 주어진 id 로 선언하고
**새로 만들어진 경우에만** `aether:runs:requested` 로 통지한다. fake 포트로, 컨테이너 없이(AR-9)."""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from aether_api.application.usecases.declare_workflow_agent_run import (
    DeclareWorkflowAgentRunUseCase,
)
from aether_api.domain.workflow_agent_run_request import WorkflowAgentRunRequest

from apps.api.tests.fakes import FakeRunDeclarationStore, FakeRunNotifier

_KEY = uuid4()


def _request(run_id: UUID | None = None, traceparent: str = "00-t-01") -> WorkflowAgentRunRequest:
    return WorkflowAgentRunRequest(
        agent_run_id=run_id or uuid4(),
        agent_version_id=uuid4(),
        input="summarize",
        traceparent=traceparent,
        requested_by=_KEY,
    )


def test_new_run_is_declared_with_the_given_id_and_notified_once() -> None:
    """spec 0005 2.5 개정 3: 실행기가 정한 id 로 선언하고 같은 id 로 통지한다."""
    store, notifier = FakeRunDeclarationStore(), FakeRunNotifier()
    request = _request()

    created = DeclareWorkflowAgentRunUseCase(store, notifier)(request)

    assert created is True
    assert store.declared_with_id == [
        (request.agent_run_id, request.agent_version_id, "summarize", _KEY)
    ], "Workflow 를 시작한 주체가 자식 Run 에 그대로 물려진다(B2)"
    assert notifier.calls == [(request.agent_run_id, request.agent_version_id, "00-t-01")]


def test_redelivered_request_declares_nothing_new_but_notifies_a_still_queued_run() -> None:
    """2026-10-14 리뷰: 재전달이어도 자식 Run 이 아직 `queued` 면 **다시 통지**한다.

    선언은 커밋됐는데 `XADD` 가 실패한 경우가 그 모양입니다. 그때 통지하지 않으면 자식 Run 이
    `queued` 로 영원히 남고 그것을 기다리는 Workflow 는 영원히 파킹됩니다 — 스위퍼는 자식의
    **종결**을 보므로 구하지 못합니다. 선언은 여전히 한 행이고(`False`) 통지만 다시 갑니다.
    """
    store, notifier = FakeRunDeclarationStore(), FakeRunNotifier()
    use_case = DeclareWorkflowAgentRunUseCase(store, notifier)
    request = _request()

    first = use_case(request)
    second = use_case(request)

    assert (first, second) == (True, False)
    assert len(store.declared_with_id) == 2, "선언 호출은 두 번이고 멱등입니다"
    assert notifier.calls == [
        (request.agent_run_id, request.agent_version_id, "00-t-01"),
        (request.agent_run_id, request.agent_version_id, "00-t-01"),
    ]


def test_redelivered_request_does_not_notify_a_run_already_picked_up() -> None:
    """이미 `running` 인 자식 Run 에는 통지하지 않는다 — 누군가 집었고, 중복 통지는 그 worker 의
    lease 와 부딪혀 PEL 에 남을 뿐입니다."""
    store, notifier = FakeRunDeclarationStore(), FakeRunNotifier()
    use_case = DeclareWorkflowAgentRunUseCase(store, notifier)
    request = _request()

    use_case(request)
    store.mark_declared_run_running(request.agent_run_id)
    second = use_case(request)

    assert second is False
    assert len(notifier.calls) == 1


def test_empty_traceparent_is_passed_through_as_empty() -> None:
    """spec 0002 2.18: 없으면 빈 문자열 -- 통지 어댑터가 그대로 싣는다."""
    store, notifier = FakeRunDeclarationStore(), FakeRunNotifier()
    request = _request(traceparent="")

    DeclareWorkflowAgentRunUseCase(store, notifier)(request)

    assert notifier.calls[0][2] == ""


def test_declaration_failure_propagates_and_notifies_nothing() -> None:
    """spec 0005 2.5 개정 3: FK 위반 같은 선언 실패는 삼키지 않고 올린다 -- 통지도 없다."""

    class _Broken(FakeRunDeclarationStore):
        def create_with_id(
            self, run_id: UUID, agent_version_id: UUID, input: str, requested_by: UUID | None
        ) -> bool:
            raise RuntimeError("fk violation")

    notifier = FakeRunNotifier()

    with pytest.raises(RuntimeError, match="fk violation"):
        DeclareWorkflowAgentRunUseCase(_Broken(), notifier)(_request())

    assert notifier.calls == []
