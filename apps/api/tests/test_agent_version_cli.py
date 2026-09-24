"""`aether-api agents get-version --agent-id --version` 서브커맨드.

spec 0002 2.2 R-1: `GetAgentVersion` 은 이미 HTTP 라우터에 붙어 있는 inbound 포트입니다
(`test_get_agent_version.py` 가 유스케이스를, `test_agents_api.py` 가 HTTP 어댑터를
검사합니다). 이 파일은 같은 포트의 두 번째 inbound 어댑터인 CLI 함수만 봅니다(AR-12) —
`FakeAgentRepository` 로 만든 `GetAgentVersionUseCase` 를 그대로 꽂아, 컨테이너 없이
"정의가 stdout 에, 메타데이터가 stderr 에, Not Found 는 종료 코드 1" 을 증명합니다.
"""

from __future__ import annotations

import json
from typing import Any
from uuid import uuid4

import pytest
from aether_api.adapters.inbound.cli import agents_get_version, build_parser
from aether_api.application.usecases.create_agent import CreateAgentUseCase
from aether_api.application.usecases.get_agent_version import GetAgentVersionUseCase
from aether_runtime.domain.agent import AgentDefinition

from apps.api.tests.fakes import FakeAgentRepository


def _definition(**overrides: Any) -> AgentDefinition:
    payload: dict[str, Any] = {"schema_version": 1, "system_prompt": "You are a helper."}
    payload.update(overrides)
    return AgentDefinition.model_validate(payload)


def test_build_parser_accepts_agents_get_version_with_agent_id_and_version() -> None:
    parser = build_parser()
    agent_id = uuid4()

    args = parser.parse_args(
        ["agents", "get-version", "--agent-id", str(agent_id), "--version", "1"]
    )

    assert args.command == "agents"
    assert args.agents_command == "get-version"
    assert args.agent_id == agent_id
    assert args.version == 1


@pytest.mark.parametrize(
    "argv",
    [
        ["agents", "get-version", "--version", "1"],
        ["agents", "get-version", "--agent-id", str(uuid4())],
        ["agents", "get-version"],
        ["agents"],
    ],
)
def test_build_parser_rejects_agents_get_version_missing_args(argv: list[str]) -> None:
    parser = build_parser()

    with pytest.raises(SystemExit):
        parser.parse_args(argv)


def test_build_parser_rejects_agents_get_version_with_non_uuid_agent_id() -> None:
    parser = build_parser()

    with pytest.raises(SystemExit):
        parser.parse_args(["agents", "get-version", "--agent-id", "not-a-uuid", "--version", "1"])


def test_agents_get_version_prints_only_definition_json_to_stdout(
    capsys: pytest.CaptureFixture[str],
) -> None:
    repo = FakeAgentRepository()
    create_agent = CreateAgentUseCase(repo)
    get_agent_version = GetAgentVersionUseCase(repo)
    agent = create_agent("weather-bot", _definition(system_prompt="v1 prompt", tools=["clock"]))

    agents_get_version(get_agent_version, agent.id, 1)

    captured = capsys.readouterr()
    printed = json.loads(captured.out)
    assert printed == _definition(system_prompt="v1 prompt", tools=["clock"]).model_dump(
        mode="json"
    )


def test_agents_get_version_writes_metadata_but_not_definition_fields_to_stderr(
    capsys: pytest.CaptureFixture[str],
) -> None:
    repo = FakeAgentRepository()
    create_agent = CreateAgentUseCase(repo)
    get_agent_version = GetAgentVersionUseCase(repo)
    agent = create_agent("weather-bot", _definition())

    agents_get_version(get_agent_version, agent.id, 1)

    captured = capsys.readouterr()
    assert f"agent_id={agent.id}" in captured.err
    assert "version=1" in captured.err


def test_agents_get_version_missing_agent_exits_1_with_agent_not_found(
    capsys: pytest.CaptureFixture[str],
) -> None:
    repo = FakeAgentRepository()
    get_agent_version = GetAgentVersionUseCase(repo)

    with pytest.raises(SystemExit) as excinfo:
        agents_get_version(get_agent_version, uuid4(), 1)

    assert excinfo.value.code == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "agent_not_found" in captured.err


def test_agents_get_version_missing_version_exits_1_with_agent_version_not_found(
    capsys: pytest.CaptureFixture[str],
) -> None:
    repo = FakeAgentRepository()
    create_agent = CreateAgentUseCase(repo)
    get_agent_version = GetAgentVersionUseCase(repo)
    agent = create_agent("weather-bot", _definition())

    with pytest.raises(SystemExit) as excinfo:
        agents_get_version(get_agent_version, agent.id, 2)

    assert excinfo.value.code == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "agent_version_not_found" in captured.err
