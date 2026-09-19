"""improvement-log 2026-09-17-001: `scripts/guard-eval-blind.sh` 가 PreToolUse hook 으로서
평가 실행(대표 task) 동안 `evaluation/tasks`·`evaluation/runs` 를 읽지 못하게 막는지 검증한다.

기준선(evaluation/runs/2026-09-17-REP-5.md, 2026-09-17-REP-8-r2.md)에서 실행 에이전트가
task 정의와 지난 판정 기록을 스스로 열어 blind 조건이 깨졌다. 이 hook 은 저장소 루트의
마커 파일 `.eval-blind` 가 있을 때만 그 두 경로를 차단한다(평상시 작업은 자유롭게 읽어야
한다). 이 테스트는 임시 디렉터리를 `--root` 로 넘기고 hook JSON 을 stdin 으로 흘려 보내
subprocess 로 검사한다 — 자체적으로 소켓을 열지 않으므로 `--disable-socket` 아래에서도
(그리고 `integration` 마크 없이) 돈다.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "scripts" / "guard-eval-blind.sh"

# Windows 의 CreateProcess 는 인자 하나짜리 "bash" 를 넘기면 System32 의 WSL 런처를
# 먼저 찾아 실패한다(실측, aether-windows-pitfalls). shutil.which 로 Git Bash 의
# 절대경로를 찾아 argv[0] 로 명시한다(tests/scripts/test_check_bench.py 와 같은 방식).
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


def test_no_marker_allows_reading_task_definition(tmp_path: Path) -> None:
    """improvement-log 2026-09-17-001: 마커가 없으면 평상시 작업이므로 아무것도 막지 않는다."""
    payload = _payload("Read", {"file_path": "evaluation/tasks/representative.md"})

    result = _run(tmp_path, payload)

    assert result.returncode == 0, result.stdout + result.stderr


def test_marker_blocks_reading_representative_task(tmp_path: Path) -> None:
    """improvement-log 2026-09-17-001: 마커가 있으면 representative.md 를 여는 Read 를 막고
    stderr 에 그 경로를 밝힌다 — REP-5 가 스스로 열어 읽은 바로 그 파일이다.
    """
    (tmp_path / ".eval-blind").touch()
    payload = _payload("Read", {"file_path": "evaluation/tasks/representative.md"})

    result = _run(tmp_path, payload)

    assert result.returncode == 2, result.stdout + result.stderr
    assert "evaluation/tasks/representative.md" in result.stderr


def test_marker_blocks_bash_reading_run_log(tmp_path: Path) -> None:
    """improvement-log 2026-09-17-001: evaluation/runs 는 지난 판정 근거와 평가자가 심은
    결함까지 담고 있어 더 직접적인 누출 경로다. 셸 명령으로 읽는 것도 막는다.
    """
    (tmp_path / ".eval-blind").touch()
    payload = _payload("Bash", {"command": "cat evaluation/runs/2026-09-17-REP-1.md"})

    result = _run(tmp_path, payload)

    assert result.returncode == 2, result.stdout + result.stderr


def test_marker_blocks_backslash_path(tmp_path: Path) -> None:
    """improvement-log 2026-09-17-001: Windows 경로는 역슬래시로 올 수 있어 두 표기 모두
    잡아야 한다(harness/hooks/guard-evaluation-tampering.sh 의 json_unescape 근거와 같은 결).
    """
    (tmp_path / ".eval-blind").touch()
    # 실제 문자열 값은 "evaluation\tasks\representative.md" (단일 백슬래시 두 곳)이며,
    # json.dumps 가 JSON 표기에 맞게 이스케이프한다.
    file_path = "evaluation\\tasks\\representative.md"
    payload = _payload("Read", {"file_path": file_path})

    result = _run(tmp_path, payload)

    assert result.returncode == 2, result.stdout + result.stderr


def test_marker_allows_reading_readme(tmp_path: Path) -> None:
    """improvement-log 2026-09-17-001: evaluation/tasks·evaluation/runs 밖의 evaluation/
    경로(예: README.md)는 blind 조건 대상이 아니므로 막지 않는다.
    """
    (tmp_path / ".eval-blind").touch()
    payload = _payload("Read", {"file_path": "evaluation/README.md"})

    result = _run(tmp_path, payload)

    assert result.returncode == 0, result.stdout + result.stderr


def test_marker_allows_unrelated_bash_command(tmp_path: Path) -> None:
    """improvement-log 2026-09-17-001: 마커가 있어도 평가 경로와 무관한 명령은 막지 않는다."""
    (tmp_path / ".eval-blind").touch()
    payload = _payload("Bash", {"command": "ls apps"})

    result = _run(tmp_path, payload)

    assert result.returncode == 0, result.stdout + result.stderr


def test_block_appends_single_log_line_with_tool_name(tmp_path: Path) -> None:
    """improvement-log 2026-09-17-001: 차단마다 `.eval-blind.log` 에 한 줄을 남겨야
    blind 조건이 실제로 작동했다는 증거가 된다(regression_check 근거).
    """
    (tmp_path / ".eval-blind").touch()
    payload = _payload("Read", {"file_path": "evaluation/tasks/representative.md"})

    result = _run(tmp_path, payload)

    assert result.returncode == 2, result.stdout + result.stderr
    log_path = tmp_path / ".eval-blind.log"
    lines = log_path.read_text(encoding="utf-8").strip("\n").splitlines()
    assert len(lines) == 1, lines
    assert "Read" in lines[0], lines[0]


def test_empty_stdin_exits_zero(tmp_path: Path) -> None:
    """improvement-log 2026-09-17-001: hook 오류(빈 입력 등)가 모든 도구 호출을 막으면
    안 되므로, stdin 이 비어 있으면 통과시킨다.
    """
    (tmp_path / ".eval-blind").touch()

    result = _run(tmp_path, "")

    assert result.returncode == 0, result.stdout + result.stderr
