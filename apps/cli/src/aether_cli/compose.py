"""`aether up` - docker compose 를 격리 프로젝트로 띄우고 내립니다 (spec 0006 요구 7, D-8).

`scripts/smoke.sh` 와 같은 방식입니다: 임시 `.env`(랜덤 비밀값)를 만들고 실행 뒤 **항상** 지웁니다.
`down -v` 는 반드시 `-p <프로젝트>` 와 함께 나갑니다 - 프로젝트 이름이 비면 compose 가 기본
프로젝트(개발 볼륨)를 대상으로 삼으므로 이름 검증이 먼저입니다(improvement-log 2026-09-22-003).
"""

from __future__ import annotations

import os
import re
import secrets
import subprocess
import tempfile
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

from aether_cli.output import write

DEFAULT_PROJECT = "aether-dev"
COMPOSE_RELATIVE = Path("infra") / "docker" / "compose.yaml"
ENV_EXAMPLE_RELATIVE = Path("infra") / "docker" / ".env.example"
# smoke.sh 와 같은 서비스 목록입니다. `web` 은 화면 단위(MVP-2)가 들어올 때 더합니다.
SERVICES = ("postgres", "redis", "migrate", "otel-collector", "api", "worker")
OTEL_OUT_RELATIVE = Path("infra") / "docker" / "out" / "otel"
PROJECT_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]*$")

_NO_COMPOSE = (
    f"error: {COMPOSE_RELATIVE.as_posix()} 를 찾지 못했습니다. 저장소 안에서 실행하십시오\n"
)

Runner = Callable[[Sequence[str]], int]


def default_runner(argv: Sequence[str]) -> int:
    return subprocess.run(list(argv), check=False).returncode


def valid_project(name: str) -> bool:
    return PROJECT_PATTERN.fullmatch(name) is not None


def find_root(start: Path) -> Path | None:
    """`start` 와 그 상위에서 `infra/docker/compose.yaml` 이 있는 저장소 루트를 찾습니다."""
    for candidate in (start, *start.parents):
        if (candidate / COMPOSE_RELATIVE).is_file():
            return candidate
    return None


def _render_env(template: str) -> str:
    lines = []
    for line in template.splitlines():
        if line.endswith("=<generate>"):
            line = f"{line.partition('=')[0]}={secrets.token_hex(24)}"
        elif line.endswith("=<optional>"):
            line = f"{line.partition('=')[0]}="
        lines.append(line)
    return "\n".join(lines) + "\n"


def _compose_prefix(project: str, env_file: str, files: Sequence[str]) -> list[str]:
    command = ["docker", "compose", "-p", project, "--env-file", env_file]
    for file in files:
        command += ["-f", file]
    return command


def _with_temp_env(root: Path, runner: Runner, build: Callable[[str], list[str]], err: Any) -> int:
    template = (root / ENV_EXAMPLE_RELATIVE).read_text(encoding="utf-8")
    descriptor, name = tempfile.mkstemp(prefix=".env.cli.", dir=root)  # `.env.*` 는 gitignore
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(_render_env(template))
        return runner(build(name))
    except FileNotFoundError:
        write(err, "error: docker 를 찾을 수 없습니다. Docker 를 설치하고 PATH 에 두십시오\n")
        return 1
    finally:
        Path(name).unlink(missing_ok=True)


def up(
    *,
    root: Path | None,
    project: str,
    extra_files: Sequence[str],
    build_images: bool,
    runner: Runner,
    api_url: str,
    out: Any,
    err: Any,
) -> int:
    resolved = root if root is not None and (root / COMPOSE_RELATIVE).is_file() else None
    if resolved is None and root is None:
        resolved = find_root(Path.cwd())
    if resolved is None:
        write(err, _NO_COMPOSE)
        return 1
    files = [str(resolved / COMPOSE_RELATIVE), *extra_files]
    otel = resolved / OTEL_OUT_RELATIVE
    otel.mkdir(parents=True, exist_ok=True)
    try:
        otel.chmod(0o777)  # Linux 에서 collector(uid 10001)가 쓰게 합니다(smoke.sh 와 같음)
    except OSError:
        pass

    def build(env_file: str) -> list[str]:
        return [
            *_compose_prefix(project, env_file, files),
            "up",
            "-d",
            "--wait",
            "--build" if build_images else "--no-build",
            *SERVICES,
        ]

    write(out, f"aether up: 스택을 띄웁니다 (project={project})\n")
    code = _with_temp_env(resolved, runner, build, err)
    if code != 0:
        write(err, f"error: docker compose up 이 {code} 로 끝났습니다\n")
        return code
    write(out, f"stack up: project={project}, api={api_url}\n")
    write(out, "다음: 키를 발급해 환경변수로 설정하십시오 (키는 발급 때 한 번만 출력됩니다)\n")
    write(
        out,
        f"  docker compose -p {project} -f {COMPOSE_RELATIVE.as_posix()} "
        "exec -T api aether-api keys create --label cli\n",
    )
    write(out, "  export AETHER_API_KEY=<위에서 출력된 값>\n")
    return 0


def down(
    *,
    root: Path | None,
    project: str,
    extra_files: Sequence[str],
    runner: Runner,
    out: Any,
    err: Any,
) -> int:
    resolved = root if root is not None and (root / COMPOSE_RELATIVE).is_file() else None
    if resolved is None and root is None:
        resolved = find_root(Path.cwd())
    if resolved is None:
        write(err, _NO_COMPOSE)
        return 1
    files = [str(resolved / COMPOSE_RELATIVE), *extra_files]

    def build(env_file: str) -> list[str]:
        return [*_compose_prefix(project, env_file, files), "down", "-v", "--remove-orphans"]

    write(out, f"aether up --down: project={project} 의 스택과 볼륨을 지웁니다\n")
    code = _with_temp_env(resolved, runner, build, err)
    if code != 0:
        write(err, f"error: docker compose down 이 {code} 로 끝났습니다\n")
    return code
