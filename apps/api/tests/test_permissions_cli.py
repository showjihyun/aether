"""🔒 spec 0003 2.14, D-14, D-6, 개정 4, P2-4: `aether-api permissions allow|deny
--agent-id --version --server --tool` 서브커맨드.

단위 테스트는 `SetToolPermission` 포트에 `SetToolPermissionUseCase` + `FakeAgentRepository`
+ `FakeToolPermissionStore`(`test_set_tool_permission.py` 와 공유)를 꽂아
`permissions_set`/`build_parser` 만 봅니다(AR-12 — CLI 어댑터는 유스케이스가 아니라
포트만 압니다). `SetToolPermissionUseCase` 자체의 동작(agent_version_id 해석·upsert·
예외 전파)과 실제 PostgreSQL 통합 테스트는 `test_set_tool_permission.py` 가 봅니다 —
이 파일은 CLI 함수(argparse·stdout/stderr 분리·종료 코드)만 봅니다.
"""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from aether_api.adapters.inbound.cli import build_parser, permissions_set
from aether_api.application.usecases.create_agent import CreateAgentUseCase
from aether_api.application.usecases.get_agent_version import GetAgentVersionUseCase
from aether_api.application.usecases.set_tool_permission import SetToolPermissionUseCase
from aether_runtime.domain.agent import AgentDefinition

from apps.api.tests.fakes import FakeAgentRepository
from apps.api.tests.test_set_tool_permission import FakeToolPermissionStore


def _definition(**overrides: Any) -> AgentDefinition:
    payload: dict[str, Any] = {"schema_version": 1, "system_prompt": "You are a helper."}
    payload.update(overrides)
    return AgentDefinition.model_validate(payload)


def test_build_parser_accepts_permissions_allow_with_all_required_args() -> None:
    parser = build_parser()
    agent_id = uuid.uuid4()

    args = parser.parse_args(
        [
            "permissions",
            "allow",
            "--agent-id",
            str(agent_id),
            "--version",
            "1",
            "--server",
            "filesystem",
            "--tool",
            "read",
        ]
    )

    assert args.command == "permissions"
    assert args.permissions_command == "allow"
    assert args.agent_id == agent_id
    assert args.version == 1
    assert args.server == "filesystem"
    assert args.tool == "read"


def test_build_parser_accepts_permissions_deny() -> None:
    parser = build_parser()

    args = parser.parse_args(
        [
            "permissions",
            "deny",
            "--agent-id",
            str(uuid.uuid4()),
            "--version",
            "1",
            "--server",
            "filesystem",
            "--tool",
            "read",
        ]
    )

    assert args.permissions_command == "deny"


@pytest.mark.parametrize(
    "argv",
    [
        ["permissions", "allow", "--version", "1", "--server", "fs", "--tool", "read"],
        ["permissions", "allow", "--agent-id", str(uuid.uuid4()), "--server", "fs", "--tool", "r"],
        ["permissions", "allow"],
        ["permissions"],
    ],
)
def test_build_parser_rejects_permissions_missing_args(argv: list[str]) -> None:
    parser = build_parser()

    with pytest.raises(SystemExit):
        parser.parse_args(argv)


def test_permissions_set_writes_confirmation_to_stderr_not_stdout(
    capsys: pytest.CaptureFixture[str],
) -> None:
    repo = FakeAgentRepository()
    create_agent = CreateAgentUseCase(repo)
    agent = create_agent("weather-bot", _definition())
    get_agent_version = GetAgentVersionUseCase(repo)
    agent_version = get_agent_version(agent.id, 1)
    store = FakeToolPermissionStore()
    set_tool_permission = SetToolPermissionUseCase(get_agent_version, store)

    permissions_set(set_tool_permission, agent.id, 1, "filesystem", "read", "allow")

    captured = capsys.readouterr()
    assert captured.out == ""
    assert "server=filesystem" in captured.err
    assert "tool=read" in captured.err
    assert "decision=allow" in captured.err
    assert store.calls == [(agent_version.id, "filesystem", "read", "allow")]


def test_permissions_set_missing_agent_exits_1_with_agent_not_found(
    capsys: pytest.CaptureFixture[str],
) -> None:
    repo = FakeAgentRepository()
    store = FakeToolPermissionStore()
    set_tool_permission = SetToolPermissionUseCase(GetAgentVersionUseCase(repo), store)

    with pytest.raises(SystemExit) as excinfo:
        permissions_set(set_tool_permission, uuid.uuid4(), 1, "filesystem", "read", "allow")

    assert excinfo.value.code == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "agent_not_found" in captured.err
    assert store.calls == []


def test_permissions_set_missing_version_exits_1_with_agent_version_not_found(
    capsys: pytest.CaptureFixture[str],
) -> None:
    repo = FakeAgentRepository()
    create_agent = CreateAgentUseCase(repo)
    agent = create_agent("weather-bot", _definition())
    store = FakeToolPermissionStore()
    set_tool_permission = SetToolPermissionUseCase(GetAgentVersionUseCase(repo), store)

    with pytest.raises(SystemExit) as excinfo:
        permissions_set(set_tool_permission, agent.id, 2, "filesystem", "read", "allow")

    assert excinfo.value.code == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "agent_version_not_found" in captured.err
    assert store.calls == []
