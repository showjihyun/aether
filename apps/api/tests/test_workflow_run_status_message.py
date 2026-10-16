"""spec 0005 2.9 개정 2, 2.10 (P4-2a A1): `WorkflowRunStatusMessage` 파싱 — 선택 필드가 없거나
있을 때, 그리고 잘못된 상태·누락 필드는 거부됩니다. 스트림 필드는 전부 문자열로 옵니다."""

from __future__ import annotations

from uuid import uuid4

import pytest
from aether_api.domain.workflow_run_status_message import WorkflowRunStatusMessage
from aether_workflow.domain.run_status import WorkflowRunStatus
from pydantic import ValidationError

_AT = "2026-01-01T00:00:00+00:00"


def test_required_fields_only() -> None:
    run_id = uuid4()

    message = WorkflowRunStatusMessage.model_validate(
        {"workflow_run_id": str(run_id), "seq": "2", "status": "running", "at": _AT}
    )

    assert message.workflow_run_id == run_id
    assert message.seq == 2
    assert message.status == WorkflowRunStatus.RUNNING
    assert message.current_node_id is None
    assert message.waiting_run_id is None
    assert message.started_at is None
    assert message.finished_at is None
    assert message.failure_reason is None


def test_all_optional_fields_present() -> None:
    run_id, child = uuid4(), uuid4()

    message = WorkflowRunStatusMessage.model_validate(
        {
            "workflow_run_id": str(run_id),
            "seq": "9",
            "status": "waiting_run",
            "at": _AT,
            "current_node_id": "a",
            "waiting_run_id": str(child),
            "started_at": "2026-01-01T00:00:01+00:00",
            "finished_at": "2026-01-01T00:00:02+00:00",
            "failure_reason": "unsupported_node_kind",
        }
    )

    assert message.status == WorkflowRunStatus.WAITING_RUN
    assert message.current_node_id == "a"
    assert message.waiting_run_id == child
    assert message.started_at is not None
    assert message.finished_at is not None
    assert message.failure_reason == "unsupported_node_kind"


@pytest.mark.parametrize(
    "fields",
    [
        {"seq": "1", "status": "running", "at": _AT},
        {"workflow_run_id": str(uuid4()), "status": "running", "at": _AT},
        {"workflow_run_id": str(uuid4()), "seq": "1", "status": "timed_out", "at": _AT},
        {"workflow_run_id": "not-a-uuid", "seq": "1", "status": "running", "at": _AT},
    ],
    ids=["no-id", "no-seq", "agent-run-only-status", "bad-id"],
)
def test_malformed_messages_are_rejected(fields: dict[str, str]) -> None:
    """`timed_out` 은 Agent Run 의 값입니다(spec 2.3 — Workflow Run 에는 없습니다)."""
    with pytest.raises(ValidationError):
        WorkflowRunStatusMessage.model_validate(fields)


def test_waiting_node_execution_id_is_parsed_and_defaults_to_none() -> None:
    """spec 0005 2.6 개정 5 (1) (P4-4): `waiting_approval` 통지는 기다리는 노드 실행의 id 를 싣고,
    없으면 `None` 이다."""
    run_id, awaited = uuid4(), uuid4()
    base = {
        "workflow_run_id": str(run_id),
        "seq": "4",
        "status": "waiting_approval",
        "at": _AT,
    }

    with_pointer = WorkflowRunStatusMessage.model_validate(
        {**base, "waiting_node_execution_id": str(awaited)}
    )
    without = WorkflowRunStatusMessage.model_validate(base)

    assert with_pointer.waiting_node_execution_id == awaited
    assert without.waiting_node_execution_id is None
