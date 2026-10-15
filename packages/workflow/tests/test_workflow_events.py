"""spec 0005 2.10, D-13: Workflow 이벤트 어휘는 자기 것이다 - 네 종류, 타입마다 payload 모델,
`aether_runtime` 을 import 하지 않는다.
"""

from __future__ import annotations

import ast
from pathlib import Path
from uuid import uuid4

import pytest
from aether_workflow.domain import events
from aether_workflow.domain.events import (
    PAYLOAD_MODELS,
    WORKFLOW_EVENT_TYPES,
    NodeFinishedPayload,
    NodeStartedPayload,
    WorkflowEvent,
    WorkflowStatusPayload,
)
from pydantic import ValidationError

from packages.workflow.tests.fakes import FakeWorkflowClock


def test_vocabulary_is_exactly_the_six_workflow_types() -> None:
    """spec 0005 2.10: 여섯 개(`approval.*` 는 P4-4)이고 Agent Run 어휘가 섞이지 않는다."""
    assert WORKFLOW_EVENT_TYPES == {
        "workflow.status",
        "node.started",
        "node.finished",
        "approval.requested",
        "approval.granted",
        "workflow.finished",
    }
    assert set(PAYLOAD_MODELS) == WORKFLOW_EVENT_TYPES


def test_status_payload_drops_absent_optional_fields() -> None:
    """선택 필드가 없으면 키 자체가 빠진다(`exclude_none`)."""
    assert WorkflowStatusPayload(status="running").model_dump(exclude_none=True) == {
        "status": "running"
    }


def test_node_payloads_carry_node_id_and_iteration() -> None:
    assert NodeStartedPayload(node_id="a", kind="START", iteration=0).model_dump() == {
        "node_id": "a",
        "kind": "START",
        "iteration": 0,
    }
    assert NodeFinishedPayload(node_id="a", iteration=0, status="succeeded").model_dump() == {
        "node_id": "a",
        "iteration": 0,
        "status": "succeeded",
    }


def test_envelope_rejects_a_foreign_type_and_a_zero_seq() -> None:
    now = FakeWorkflowClock().now()
    with pytest.raises(ValidationError):
        WorkflowEvent.model_validate(
            {
                "workflow_run_id": str(uuid4()),
                "seq": 1,
                "at": now,
                "type": "task.started",
                "payload": {},
            }
        )
    with pytest.raises(ValidationError):
        WorkflowEvent(
            workflow_run_id=uuid4(),
            seq=0,
            at=now,
            type="workflow.status",
            payload={},
        )


def test_events_module_does_not_import_the_agent_run_vocabulary() -> None:
    """D-13, AR-13: 어휘가 다른 것을 한 계약에 섞지 않는다 - 코드도 공유하지 않는다."""
    tree = ast.parse(Path(events.__file__).read_text(encoding="utf-8"))
    imported = {
        node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)
    } | {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    assert not any(name.startswith("aether_runtime") for name in imported)
