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


def test_no_new_lease_or_sweeper_variable_is_introduced() -> None:
    """lease TTL 은 기존 `worker_lease_seconds`, 스위퍼 주기는 PR B 의 몫이다."""
    names = set(Settings.model_fields)
    assert not {n for n in names if "sweep" in n}
    assert not {n for n in names if n.startswith("workflow_") and "lease" in n}
