"""spec 0005 2.9 개정 2 (P4-2a A): worker `Settings` 의 Workflow 변수 - 스트림 이름은 A1 계약이고,
Agent Run 의 스트림과 **다르다**. lease TTL 은 새 변수 없이 기존 `worker_lease_seconds` 를 쓴다.
"""

from __future__ import annotations

import pytest
from aether_worker.settings import Settings


def test_workflow_stream_defaults_are_the_a1_contract_and_not_the_run_streams() -> None:
    settings = Settings()

    assert settings.workflow_stream == "aether:workflow_runs:requested"
    assert settings.workflow_status_stream == "aether:workflow_runs:status"
    assert settings.workflow_group == "aether-worker"
    assert settings.workflow_stream != settings.worker_stream
    assert settings.workflow_status_stream != settings.worker_status_stream


def test_workflow_streams_can_be_overridden_by_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AETHER_WORKFLOW_STREAM", "x:requested")
    monkeypatch.setenv("AETHER_WORKFLOW_STATUS_STREAM", "x:status")

    settings = Settings()

    assert settings.workflow_stream == "x:requested"
    assert settings.workflow_status_stream == "x:status"


def test_sweep_interval_defaults_to_30_seconds_and_can_be_overridden(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """spec 0005 2.11 (P4-2a B2): 스위퍼 주기 `AETHER_WORKFLOW_SWEEP_INTERVAL_SECONDS`, 기본 30."""
    assert Settings().workflow_sweep_interval_seconds == 30.0

    monkeypatch.setenv("AETHER_WORKFLOW_SWEEP_INTERVAL_SECONDS", "2.5")

    assert Settings().workflow_sweep_interval_seconds == 2.5


def test_wake_group_is_the_workflow_only_group_and_not_the_api_projection_group() -> None:
    """spec 0005 2.5 개정 3: 빠른 경로는 `aether:runs:status` 를 Workflow 전용 group 으로 읽는다 -
    Agent Run 의 api 쪽 투영 group(`aether-api`)과 다른 이름이다."""
    settings = Settings()

    assert settings.workflow_wake_group == "aether-workflow"
    assert settings.workflow_wake_group != "aether-api"
    assert settings.worker_status_stream == "aether:runs:status"


def test_no_new_lease_variable_is_introduced() -> None:
    """lease TTL 은 새 변수 없이 기존 `worker_lease_seconds` 를 쓴다."""
    names = set(Settings.model_fields)
    assert not {n for n in names if n.startswith("workflow_") and "lease" in n}


def test_node_output_limit_defaults_to_8_kib_and_can_be_overridden(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """spec 0005 2.4 개정 4 (P4-2b): 노드 출력의 상한(직렬화된 바이트) -
    `AETHER_WORKFLOW_NODE_OUTPUT_MAX_BYTES`, 기본 8192."""
    assert Settings().workflow_node_output_max_bytes == 8192

    monkeypatch.setenv("AETHER_WORKFLOW_NODE_OUTPUT_MAX_BYTES", "256")

    assert Settings().workflow_node_output_max_bytes == 256


def test_node_output_limit_below_the_envelope_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    """`{"text":"","status":"timed_out"}` 조차 담지 못하는 상한은 설정 오류다 - 조용히 빈 출력을
    만들지 않는다."""
    monkeypatch.setenv("AETHER_WORKFLOW_NODE_OUTPUT_MAX_BYTES", "8")

    with pytest.raises(ValueError, match="workflow_node_output_max_bytes"):
        Settings()


def test_node_status_stream_is_its_own_stream(monkeypatch: pytest.MonkeyPatch) -> None:
    """spec 0007 P5-1: 노드 실행 투영 통지는 **새 스트림**이다 - 소비자 둘인 기존
    `aether:workflow_runs:status` 를 넓히지 않는다. 환경으로 바꿀 수 있다."""
    settings = Settings()

    assert settings.workflow_node_status_stream == "aether:workflow_node_states:status"
    assert settings.workflow_node_status_stream != settings.workflow_status_stream

    monkeypatch.setenv("AETHER_WORKFLOW_NODE_STATUS_STREAM", "x:nodes")
    assert Settings().workflow_node_status_stream == "x:nodes"
