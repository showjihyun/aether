"""spec 0006 R-1 (MVP-1): CLI **서브프로세스**로 격리 compose 에서 Agent 생성 -> Run -> 상태 조회.

`api-integration`. `scripts/smoke.sh` 와 같은 격리 방식이다 - 고정 프로젝트 `aether-cli-it`,
임시 `.env`(`aether up` 이 만들고 지운다), 끝나면 `aether up --down` 으로 정리한다(개발 스택은
건드리지 않는다). 모델은 fake(`.env.example` 기본값)라 네트워크가 필요 없다. `SMOKE_NO_BUILD=1`
이면 smoke 와 같이 `compose.ci.yaml` 의 미리 빌드된 이미지를 쓴다.

키 원문은 어떤 단언 메시지에도 싣지 않는다(D-8).
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import uuid
from collections.abc import Iterator
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration

ROOT = Path(__file__).resolve().parents[3]
PROJECT = "aether-cli-it"
STACK_TIMEOUT_SECONDS = 900
COMMAND_TIMEOUT_SECONDS = 120


def _free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def _aether(
    args: list[str], env: dict[str, str], timeout: int = COMMAND_TIMEOUT_SECONDS
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "aether_cli", *args],
        cwd=ROOT,
        env=env,
        capture_output=True,
        timeout=timeout,
        check=False,
        text=True,
        encoding="utf-8",
    )


def _api_container() -> str:
    found = subprocess.run(
        [
            "docker",
            "ps",
            "-q",
            "--filter",
            f"label=com.docker.compose.project={PROJECT}",
            "--filter",
            "label=com.docker.compose.service=api",
        ],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.split()
    assert len(found) == 1, f"api container of project {PROJECT} not found: {found}"
    return found[0]


@pytest.fixture(scope="module")
def stack(tmp_path_factory: pytest.TempPathFactory) -> Iterator[dict[str, str]]:
    port = _free_port()
    override = tmp_path_factory.mktemp("aether-cli-it") / "compose.ports.yaml"
    override.write_text(
        f'services:\n  api:\n    ports: !override ["127.0.0.1:{port}:8000"]\n', encoding="utf-8"
    )
    otel = ROOT / "infra" / "docker" / "out" / "otel-smoke"
    otel.mkdir(parents=True, exist_ok=True)
    otel.chmod(0o777)

    files = ["--compose-file", "infra/docker/compose.smoke.yaml", "--compose-file", str(override)]
    build = []
    if os.environ.get("SMOKE_NO_BUILD") == "1":
        files += ["--compose-file", "infra/docker/compose.ci.yaml"]
        build = ["--no-build"]
    base_env = {**os.environ, "AETHER_API_URL": f"http://127.0.0.1:{port}"}
    base_env.pop("AETHER_API_KEY", None)

    try:
        up = _aether(["up", "--project", PROJECT, *files, *build], base_env, STACK_TIMEOUT_SECONDS)
        assert up.returncode == 0, f"aether up failed:\n{up.stdout}\n{up.stderr}"
        issued = subprocess.run(
            [
                "docker",
                "exec",
                _api_container(),
                "aether-api",
                "keys",
                "create",
                "--label",
                "cli-it",
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        key = issued.stdout.strip()
        assert key, "key was not issued"
        yield {**base_env, "AETHER_API_KEY": key}
    finally:
        down = _aether(
            ["up", "--down", "--project", PROJECT, *files], base_env, STACK_TIMEOUT_SECONDS
        )
        leftover = subprocess.run(
            ["docker", "ps", "-aq", "--filter", f"label=com.docker.compose.project={PROJECT}"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.split()
        assert down.returncode == 0 and leftover == [], (
            f"cleanup failed: exit={down.returncode} leftover={leftover}"
        )
        assert list(ROOT.glob(".env.cli.*")) == [], "temp .env was not removed"


def test_create_run_and_get_through_the_cli_alone(stack: dict[str, str]) -> None:
    """R-1: CLI 만으로 Agent 생성 -> Run(스트림 출력) -> 상태 조회, 마지막 상태가 `succeeded`."""
    key = stack["AETHER_API_KEY"]

    created = _aether(
        ["agent", "create", "--name", f"cli-it-{uuid.uuid4()}", "--prompt", "p"], stack
    )
    assert created.returncode == 0, created.stderr.replace(key, "***")
    agent_id = created.stdout.strip()
    uuid.UUID(agent_id)

    listed = _aether(["agent", "list"], stack)
    assert listed.returncode == 0 and agent_id in listed.stdout

    ran = _aether(["run", agent_id, "--input", "안녕하세요"], stack)
    assert ran.returncode == 0, ran.stdout + ran.stderr.replace(key, "***")
    lines = ran.stdout.splitlines()
    event_lines = [line for line in lines if line.split() and line.split()[0].isdigit()]
    assert len(event_lines) >= 3, ran.stdout  # 이벤트가 한 줄씩 나타난다
    assert "run.finished" in event_lines[-1]
    seqs = [int(line.split()[0]) for line in event_lines]
    assert seqs == sorted(seqs) and seqs[0] == 1
    assert lines[-1] == "status: succeeded"

    run_id = next(line.removeprefix("run: ") for line in lines if line.startswith("run: "))
    got = _aether(["runs", "get", run_id], stack)
    assert got.returncode == 0, got.stderr.replace(key, "***")
    assert "status: succeeded" in got.stdout

    for result in (created, listed, ran, got):
        assert key not in result.stdout + result.stderr, "API key leaked into CLI output"


def test_a_wrong_key_is_rejected_without_echoing_it(stack: dict[str, str]) -> None:
    """D-8: 잘못된 키는 401 로 exit 1, 그 키는 출력에 없다."""
    wrong = "aether_sk_wrong_" + uuid.uuid4().hex

    result = _aether(["agent", "list"], {**stack, "AETHER_API_KEY": wrong})

    assert result.returncode == 1
    assert "401" in result.stderr
    assert wrong not in result.stdout + result.stderr
