"""`aether up` - compose 를 격리 프로젝트로 띄우고 내린다. docker 는 부르지 않는다(runner fake)."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

import pytest
from aether_cli.main import main

from apps.cli.tests.fakes_aether_cli import Cp949Console

ENV_EXAMPLE = (
    "POSTGRES_PASSWORD=<generate>\n"
    "POSTGRES_USER=aether_admin\n"
    "AETHER_MODEL_ADAPTER=fake\n"
    "AETHER_MODEL_API_KEY=<optional>\n"
    "AETHER_CONTROL_PASSWORD=<generate>\n"
)


class Runner:
    def __init__(self, code: int = 0) -> None:
        self.code = code
        self.commands: list[list[str]] = []
        self.env_texts: list[str] = []
        self.env_paths: list[Path] = []

    def __call__(self, argv: Sequence[str]) -> int:
        self.commands.append(list(argv))
        if "--env-file" in argv:
            path = Path(argv[list(argv).index("--env-file") + 1])
            self.env_paths.append(path)
            self.env_texts.append(path.read_text(encoding="utf-8"))  # 실행 중에는 있어야 한다
        return self.code


@pytest.fixture
def root(tmp_path: Path) -> Path:
    compose_dir = tmp_path / "infra" / "docker"
    compose_dir.mkdir(parents=True)
    (compose_dir / "compose.yaml").write_text("services: {}\n", encoding="utf-8")
    (compose_dir / ".env.example").write_text(ENV_EXAMPLE, encoding="utf-8")
    return tmp_path


def _run(argv: list[str], root: Path, runner: Runner) -> tuple[int, str, str]:
    out, err = Cp949Console(), Cp949Console()
    code = main(argv, env={}, stdout=out, stderr=err, runner=runner, root=root)
    return code, out.text(), err.text()


def test_up_needs_no_api_key_and_uses_the_isolated_project(root: Path) -> None:
    """spec 0006 요구 7: 키 없이도 되고 `-p aether-dev` 고정 이름으로 띄운다."""
    runner = Runner()

    code, out, err = _run(["up"], root, runner)

    assert code == 0, err
    command = runner.commands[0]
    assert command[:2] == ["docker", "compose"]
    assert command[command.index("-p") + 1] == "aether-dev"
    assert "up" in command and "-d" in command and "--wait" in command
    assert "AETHER_API_KEY" in out  # 다음 단계 안내


def test_up_writes_a_temp_env_with_generated_secrets_and_removes_it(root: Path) -> None:
    """요구 7·D-8: 임시 `.env` 에 랜덤 비밀값, 끝나면 지운다. 비밀값은 출력에 없다."""
    runner = Runner()

    code, out, err = _run(["up"], root, runner)

    assert code == 0, err
    text = runner.env_texts[0]
    assert "<generate>" not in text and "<optional>" not in text
    values = dict(line.split("=", 1) for line in text.splitlines())
    assert len(values["POSTGRES_PASSWORD"]) >= 32
    assert values["POSTGRES_PASSWORD"] != values["AETHER_CONTROL_PASSWORD"]
    assert values["POSTGRES_USER"] == "aether_admin"
    assert values["AETHER_MODEL_API_KEY"] == ""
    assert not runner.env_paths[0].exists()
    assert values["POSTGRES_PASSWORD"] not in out + err


def test_up_removes_the_temp_env_even_when_compose_fails(root: Path) -> None:
    """compose 가 실패해도 임시 `.env` 를 남기지 않고, 그 종료 코드가 0 이 아니다."""
    runner = Runner(code=1)

    code, _out, _err = _run(["up"], root, runner)

    assert code != 0
    assert not runner.env_paths[0].exists()
    assert list(root.glob(".env*")) == []


def test_down_removes_volumes_only_inside_the_named_project(root: Path) -> None:
    """요구 7: `down -v` 는 항상 `-p <프로젝트>` 와 함께다 - 다른 스택을 지우지 않는다."""
    runner = Runner()

    code, _out, err = _run(["up", "--down", "--project", "aether-cli-it"], root, runner)

    assert code == 0, err
    command = runner.commands[0]
    assert command[command.index("-p") + 1] == "aether-cli-it"
    assert command[command.index("down") :] == ["down", "-v", "--remove-orphans"]
    assert not runner.env_paths[0].exists()


@pytest.mark.parametrize("project", ["", "  ", "bad name", "-x"])
def test_an_invalid_project_name_is_refused_before_running_docker(root: Path, project: str) -> None:
    """프로젝트 이름이 비면 compose 가 기본 프로젝트(개발 볼륨)를 대상으로 삼는다 - 거부한다."""
    runner = Runner()

    code, _out, _err = _run(["up", "--down", "--project", project], root, runner)

    assert code == 2
    assert runner.commands == []


def test_extra_compose_files_follow_the_base_file(root: Path) -> None:
    """`--compose-file` 로 override 를 더할 수 있다(통합 테스트가 포트를 바꾼다)."""
    runner = Runner()

    code, _out, err = _run(["up", "--compose-file", "extra.yaml", "--no-build"], root, runner)

    assert code == 0, err
    command = runner.commands[0]
    files = [command[i + 1] for i, token in enumerate(command) if token == "-f"]
    assert files[0].endswith("compose.yaml") and files[1] == "extra.yaml"
    assert "--no-build" in command and "--build" not in command


def test_up_outside_the_repository_explains_where_to_run(tmp_path: Path) -> None:
    """compose 파일을 못 찾으면 exit 1 과 안내 - docker 를 부르지 않는다."""
    runner = Runner()

    code, _out, err = _run(["up"], tmp_path, runner)

    assert code == 1
    assert "compose.yaml" in err
    assert runner.commands == []
