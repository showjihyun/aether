"""improvement-log 2026-09-22-003: `scripts/guard-docker-volumes.sh` 가 PreToolUse hook 으로서
기본 compose 프로젝트의 개발 볼륨 삭제를 막는지 검증한다.

기준선(2026-09-23 REP-4 평가 실행)에서 실행자가 격리 프로젝트(`-p`) 없이 기본 개발 compose
프로젝트로 스택을 띄웠다가 `docker compose ... down -v` 로 정리하면서, 실행 전부터 있던 개발
볼륨 `docker_postgres_data`·`docker_redis_data` 를 되돌릴 수 없이 지웠다. 이 hook 은 마커
파일에 의존하지 않고 항상 다음을 막는다 — 격리 프로젝트 지정 없는 `docker compose down -v`
(및 `--volumes`), `docker_` 접두사 볼륨을 대상으로 하는 `docker volume rm`, `--volumes`
옵션이 있는 `docker volume prune`·`docker system prune`. 입력 파싱·종료 코드 규약·로그 방식은
`scripts/guard-eval-blind.sh`(및 그 테스트 `test_guard_eval_blind.py`)와 같은 방식을 따른다 —
`--root` 로 임시 디렉터리를 넘기고 hook JSON 을 stdin 으로 흘려 보내 subprocess 로 검사하므로
`--disable-socket` 아래에서도 돈다.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "scripts" / "guard-docker-volumes.sh"

# Windows 의 CreateProcess 는 인자 하나짜리 "bash" 를 넘기면 System32 의 WSL 런처를
# 먼저 찾아 실패한다(실측, aether-windows-pitfalls). shutil.which 로 Git Bash 의
# 절대경로를 찾아 argv[0] 로 명시한다(tests/scripts/test_guard_eval_blind.py 와 같은 방식).
_BASH = shutil.which("bash") or "bash"


def _run(root: Path, payload: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [_BASH, str(SCRIPT_PATH), "--root", str(root)],
        input=payload,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )


def _payload(tool_name: str, tool_input: dict[str, str]) -> str:
    return json.dumps({"tool_name": tool_name, "tool_input": tool_input})


def test_blocks_default_project_down_dash_v(tmp_path: Path) -> None:
    """AD-2 2026-09-22-003: 격리 프로젝트 지정 없는 `docker compose down -v` 를 막는다 —
    REP-4 평가 실행에서 실제로 개발 볼륨을 지운 명령이다."""
    payload = _payload("Bash", {"command": "docker compose -f infra/docker/compose.yaml down -v"})

    result = _run(tmp_path, payload)

    assert result.returncode == 2, result.stdout + result.stderr


def test_blocks_default_project_down_long_volumes_flag(tmp_path: Path) -> None:
    """AD-2 2026-09-22-003: `--volumes` 장문 플래그도 `-v` 와 동일하게 막는다."""
    payload = _payload(
        "Bash", {"command": "docker compose -f infra/docker/compose.yaml down --volumes"}
    )

    result = _run(tmp_path, payload)

    assert result.returncode == 2, result.stdout + result.stderr


def test_blocks_project_name_docker_treated_as_default(tmp_path: Path) -> None:
    """AD-2 2026-09-22-003: 프로젝트 이름이 `docker`(compose 의 기본 프로젝트 이름)이면
    명시적으로 지정했더라도 격리로 인정하지 않고 막는다."""
    payload = _payload("Bash", {"command": "docker compose -p docker down -v"})

    result = _run(tmp_path, payload)

    assert result.returncode == 2, result.stdout + result.stderr


def test_blocks_volume_rm_docker_prefixed_volume(tmp_path: Path) -> None:
    """AD-2 2026-09-22-003: `docker_` 접두사 볼륨을 대상으로 하는 `docker volume rm` 을 막는다
    — REP-4 에서 지워진 `docker_postgres_data` 형태다."""
    payload = _payload("Bash", {"command": "docker volume rm docker_postgres_data"})

    result = _run(tmp_path, payload)

    assert result.returncode == 2, result.stdout + result.stderr


def test_blocks_volume_prune_with_volumes_flag(tmp_path: Path) -> None:
    """AD-2 2026-09-22-003: `docker volume prune --volumes` (실제로는 항상 볼륨을 지우지만
    스펙이 명시한 `--volumes` 케이스)를 막는다."""
    payload = _payload("Bash", {"command": "docker volume prune --volumes -f"})

    result = _run(tmp_path, payload)

    assert result.returncode == 2, result.stdout + result.stderr


def test_blocks_system_prune_with_volumes_flag(tmp_path: Path) -> None:
    """AD-2 2026-09-22-003: `docker system prune --volumes` 는 개발 볼륨까지 함께 지우므로
    막는다."""
    payload = _payload("Bash", {"command": "docker system prune --volumes -f"})

    result = _run(tmp_path, payload)

    assert result.returncode == 2, result.stdout + result.stderr


def test_allows_isolated_project_flag_down_dash_v(tmp_path: Path) -> None:
    """AD-2 2026-09-22-003: `-p aether-smoke` 처럼 격리 프로젝트를 지정한 `down -v` 는
    막지 않는다 — `scripts/smoke.sh` 가 쓰는 방식이다."""
    payload = _payload(
        "Bash",
        {"command": "docker compose -p aether-smoke -f infra/docker/compose.yaml down -v"},
    )

    result = _run(tmp_path, payload)

    assert result.returncode == 0, result.stdout + result.stderr


def test_allows_isolated_project_name_long_flag_down_volumes(tmp_path: Path) -> None:
    """AD-2 2026-09-22-003: `--project-name <이름>` 형태의 격리 지정도 인정한다."""
    payload = _payload(
        "Bash",
        {"command": "docker compose --project-name aether-smoke down --volumes"},
    )

    result = _run(tmp_path, payload)

    assert result.returncode == 0, result.stdout + result.stderr


def test_allows_isolated_project_name_equals_flag(tmp_path: Path) -> None:
    """AD-2 2026-09-22-003: `--project-name=<이름>` 등호 표기도 격리로 인정한다."""
    payload = _payload(
        "Bash",
        {"command": "docker compose --project-name=aether-smoke down -v"},
    )

    result = _run(tmp_path, payload)

    assert result.returncode == 0, result.stdout + result.stderr


def test_allows_isolated_compose_project_name_env_var(tmp_path: Path) -> None:
    """AD-2 2026-09-22-003: 명령 앞의 `COMPOSE_PROJECT_NAME=<이름>` 환경변수 대입도
    격리 지정으로 인정한다."""
    payload = _payload(
        "Bash",
        {"command": "COMPOSE_PROJECT_NAME=aether-smoke docker compose down -v"},
    )

    result = _run(tmp_path, payload)

    assert result.returncode == 0, result.stdout + result.stderr


def test_allows_down_without_volumes_flag(tmp_path: Path) -> None:
    """AD-2 2026-09-22-003: `-v` 없는 `docker compose down` 은 컨테이너만 내리므로
    막지 않는다."""
    payload = _payload("Bash", {"command": "docker compose down"})

    result = _run(tmp_path, payload)

    assert result.returncode == 0, result.stdout + result.stderr


def test_allows_volume_rm_non_docker_prefixed_volume(tmp_path: Path) -> None:
    """AD-2 2026-09-22-003: `docker_` 접두사가 아닌 볼륨(격리 프로젝트가 만든 볼륨)은
    막지 않는다."""
    payload = _payload("Bash", {"command": "docker volume rm aether-smoke_postgres_data"})

    result = _run(tmp_path, payload)

    assert result.returncode == 0, result.stdout + result.stderr


def test_allows_compose_up(tmp_path: Path) -> None:
    """AD-2 2026-09-22-003: `docker compose up` 등 그 밖의 명령은 막지 않는다."""
    payload = _payload("Bash", {"command": "docker compose -f infra/docker/compose.yaml up -d"})

    result = _run(tmp_path, payload)

    assert result.returncode == 0, result.stdout + result.stderr


def test_allows_compose_ps_and_logs(tmp_path: Path) -> None:
    """AD-2 2026-09-22-003: `docker compose ps`·`logs` 는 막지 않는다."""
    payload = _payload("Bash", {"command": "docker compose ps && docker compose logs"})

    result = _run(tmp_path, payload)

    assert result.returncode == 0, result.stdout + result.stderr


def test_allows_docker_word_in_path_no_false_positive(tmp_path: Path) -> None:
    """AD-2 2026-09-22-003: `docker` 라는 낱말이 경로에 들어간 산문 명령은 오탐이 나면
    안 된다."""
    payload = _payload(
        "Bash",
        {"command": "cat infra/docker/compose.yaml && ls infra/docker"},
    )

    result = _run(tmp_path, payload)

    assert result.returncode == 0, result.stdout + result.stderr


def test_block_message_explains_reason_and_remedy(tmp_path: Path) -> None:
    """AD-2 2026-09-22-003: 차단 메시지는 무엇을 왜 막았는지와 대안(`-p <이름>` 격리)을
    담아야 한다."""
    payload = _payload("Bash", {"command": "docker compose down -v"})

    result = _run(tmp_path, payload)

    assert result.returncode == 2, result.stdout + result.stderr
    assert "-p" in result.stderr, result.stderr
    assert "2026-09-22-003" in result.stderr, result.stderr


def test_block_appends_single_log_line(tmp_path: Path) -> None:
    """AD-2 2026-09-22-003: 차단마다 `.harness/guard-volume-events.log` 에 한 줄을 남겨
    실제로 작동했다는 증거를 남긴다."""
    payload = _payload("Bash", {"command": "docker compose down -v"})

    result = _run(tmp_path, payload)

    assert result.returncode == 2, result.stdout + result.stderr
    log_path = tmp_path / ".harness" / "guard-volume-events.log"
    lines = log_path.read_text(encoding="utf-8").strip("\n").splitlines()
    assert len(lines) == 1, lines
    assert "Bash" in lines[0], lines[0]
    assert "docker compose down -v" in lines[0], lines[0]


def test_empty_stdin_exits_zero(tmp_path: Path) -> None:
    """AD-2 2026-09-22-003: hook 오류(빈 입력 등)가 모든 도구 호출을 막으면 안 되므로,
    stdin 이 비어 있으면 통과시킨다."""
    result = _run(tmp_path, "")

    assert result.returncode == 0, result.stdout + result.stderr


def test_non_bash_tool_is_not_blocked(tmp_path: Path) -> None:
    """AD-2 2026-09-22-003: command 필드가 없는 도구 호출(예: Read)은 검사 대상이 아니다."""
    payload = _payload("Read", {"file_path": "infra/docker/compose.yaml"})

    result = _run(tmp_path, payload)

    assert result.returncode == 0, result.stdout + result.stderr
