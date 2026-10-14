"""spec 0005 2.5 개정 3 (P4-2a B1): `WorkflowAgentRunRequest` 파싱 -- 스트림 계약의
필드(`requested_by` 추가: B2).
스트림 필드는 전부 문자열로 옵니다."""

from __future__ import annotations

from uuid import uuid4

import pytest
from aether_api.domain.workflow_agent_run_request import WorkflowAgentRunRequest
from pydantic import ValidationError


def test_four_contract_fields_parse() -> None:
    run_id, version_id = uuid4(), uuid4()

    request = WorkflowAgentRunRequest.model_validate(
        {
            "agent_run_id": str(run_id),
            "agent_version_id": str(version_id),
            "input": "hi",
            "traceparent": "00-a-b-01",
        }
    )

    assert (request.agent_run_id, request.agent_version_id) == (run_id, version_id)
    assert (request.input, request.traceparent) == ("hi", "00-a-b-01")


def test_empty_input_and_missing_traceparent_are_accepted() -> None:
    """`control.runs.input` 은 NOT NULL 이지 빈 값을 막는 열이 아니다. traceparent 가 빠지면
    빈 문자열."""
    request = WorkflowAgentRunRequest.model_validate(
        {"agent_run_id": str(uuid4()), "agent_version_id": str(uuid4()), "input": ""}
    )

    assert request.input == ""
    assert request.traceparent == ""


@pytest.mark.parametrize("missing", ["agent_run_id", "agent_version_id", "input"])
def test_missing_required_field_is_rejected(missing: str) -> None:
    fields = {"agent_run_id": str(uuid4()), "agent_version_id": str(uuid4()), "input": "x"}
    del fields[missing]

    with pytest.raises(ValidationError):
        WorkflowAgentRunRequest.model_validate(fields)


def test_non_uuid_run_id_is_rejected() -> None:
    with pytest.raises(ValidationError):
        WorkflowAgentRunRequest.model_validate(
            {"agent_run_id": "nope", "agent_version_id": str(uuid4()), "input": "x"}
        )


def test_requested_by_is_the_workflow_starter_and_empty_means_none() -> None:
    """B2: 자식 Run 이 물려받는 요청자. 와이어에서 비어 있으면(빈 문자열) `None`, 없어도 `None`."""
    key = uuid4()
    base = {"agent_run_id": str(uuid4()), "agent_version_id": str(uuid4()), "input": "x"}

    with_key = WorkflowAgentRunRequest.model_validate({**base, "requested_by": str(key)})
    empty = WorkflowAgentRunRequest.model_validate({**base, "requested_by": ""})
    absent = WorkflowAgentRunRequest.model_validate(base)

    assert with_key.requested_by == key
    assert empty.requested_by is None
    assert absent.requested_by is None


def test_non_uuid_requested_by_is_rejected() -> None:
    with pytest.raises(ValidationError):
        WorkflowAgentRunRequest.model_validate(
            {
                "agent_run_id": str(uuid4()),
                "agent_version_id": str(uuid4()),
                "input": "x",
                "requested_by": "someone",
            }
        )
