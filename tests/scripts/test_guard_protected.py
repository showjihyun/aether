"""AD-2 (improvement-log 2026-09-23-001): 보호 파일 취급을 **증거**와 **게이트**로 나눈다.

2026-09-24~25 라운드 실측 — 사람이 실행해야 했던 블록 12회 중 3회가 조용히 실패했고
(브랜치 불일치, `gh` 버그), 블록 내용은 대부분 `evaluation/runs/**`(실행 기록, 증거)였다.
그것은 게이트(합격 기준·harness.config·CI 워크플로·훅 설정)가 아니다. `guard-protected.sh`
는 PreToolUse hook 래퍼로서, stdin 의 hook JSON 이 참조하는 보호 경로가 **오직** 루트
`evaluation/runs/` 아래일 때만 직접 허용하고, 그 밖에는 번들 `guard-evaluation-tampering.sh`
에 그대로 위임한다(그 종료 코드·stderr 를 그대로 전달). 이 테스트는 임시 루트에 번들 가드
(harness/ 전체)를 복사해 두고 `--root` 로 넘겨 subprocess 로 검사한다 — 소켓을 열지 않으므로
`--disable-socket` 아래에서도 돈다.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "scripts" / "guard-protected.sh"

# Windows 의 CreateProcess 는 인자 하나짜리 "bash" 를 넘기면 System32 의 WSL 런처를
# 먼저 찾아 실패한다(실측, aether-windows-pitfalls). shutil.which 로 Git Bash 의
# 절대경로를 찾아 argv[0] 로 명시한다.
_BASH = shutil.which("bash") or "bash"


def _copy_bundle(root: Path) -> None:
    """번들 가드(harness/ 전체)를 임시 루트에 복사한다 — 진짜 파일을 복사한다."""
    shutil.copytree(REPO_ROOT / "harness", root / "harness")


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


def test_evidence_path_write_is_allowed_and_logged(tmp_path: Path) -> None:
    """AD-2 2026-09-23-001: evaluation/runs/ 아래 쓰기는 실행 기록(증거)이지 게이트가
    아니므로 허용하고, 누가 무엇을 지나갔는지 감사할 수 있게 허용 로그를 남긴다.
    """
    _copy_bundle(tmp_path)
    payload = _payload(
        "Write",
        {
            "file_path": "evaluation/runs/2026-09-24-REP-1-seeded.md",
            "content": "x",
        },
    )

    result = _run(tmp_path, payload)

    assert result.returncode == 0, result.stdout + result.stderr
    log_path = tmp_path / ".harness" / "guard-evidence-allow.log"
    lines = log_path.read_text(encoding="utf-8").strip("\n").splitlines()
    assert len(lines) == 1, lines
    assert "Write" in lines[0], lines[0]
    assert "evaluation/runs/2026-09-24-REP-1-seeded.md" in lines[0], lines[0]


def test_gate_path_evaluation_tasks_is_delegated_and_blocked(tmp_path: Path) -> None:
    """AD-2 2026-09-23-001: evaluation/tasks/ (합격 기준)는 증거가 아니라 게이트이므로
    번들 가드에 위임해 차단하고, 번들 가드의 메시지가 stderr 에 그대로 나온다.
    """
    _copy_bundle(tmp_path)
    payload = _payload("Write", {"file_path": "evaluation/tasks/representative.md", "content": "x"})

    result = _run(tmp_path, payload)

    assert result.returncode == 2, result.stdout + result.stderr
    assert "evaluation/tasks/representative.md" in result.stderr, result.stderr


def test_harness_config_is_delegated_and_blocked(tmp_path: Path) -> None:
    """AD-2 2026-09-23-001: harness.config 는 게이트 정의 자체이므로 위임해 차단한다."""
    _copy_bundle(tmp_path)
    payload = _payload("Write", {"file_path": "harness.config", "content": "x"})

    result = _run(tmp_path, payload)

    assert result.returncode == 2, result.stdout + result.stderr


def test_ci_workflow_is_delegated_and_blocked(tmp_path: Path) -> None:
    """AD-2 2026-09-23-001: CI 워크플로는 게이트이므로 위임해 차단한다."""
    _copy_bundle(tmp_path)
    payload = _payload("Write", {"file_path": ".github/workflows/harness.yml", "content": "x"})

    result = _run(tmp_path, payload)

    assert result.returncode == 2, result.stdout + result.stderr


def test_claude_settings_is_delegated_and_blocked(tmp_path: Path) -> None:
    """AD-2 2026-09-23-001: 훅 등록(.claude/settings.json)은 게이트의 실행 조건이므로
    위임해 차단한다.
    """
    _copy_bundle(tmp_path)
    payload = _payload("Write", {"file_path": ".claude/settings.json", "content": "x"})

    result = _run(tmp_path, payload)

    assert result.returncode == 2, result.stdout + result.stderr


def test_unprotected_path_is_allowed(tmp_path: Path) -> None:
    """AD-2 2026-09-23-001: 보호 대상이 아닌 경로는 위임해도 번들 가드가 통과시킨다."""
    _copy_bundle(tmp_path)
    payload = _payload("Write", {"file_path": "apps/api/src/x.py", "content": "x"})

    result = _run(tmp_path, payload)

    assert result.returncode == 0, result.stdout + result.stderr


def test_command_mixing_evidence_and_gate_paths_is_delegated_and_blocked(
    tmp_path: Path,
) -> None:
    """AD-2 2026-09-23-001: 한 명령이 증거 경로와 게이트 경로를 함께 건드리면 판정하기
    어려우므로 위임한다(즉 막는다) — 증거 예외로 게이트 변경을 숨기지 못하게 한다.
    """
    _copy_bundle(tmp_path)
    payload = _payload(
        "Bash",
        {
            "command": "cat evaluation/runs/2026-09-24-REP-1.md >> harness.config",
        },
    )

    result = _run(tmp_path, payload)

    assert result.returncode == 2, result.stdout + result.stderr


def test_empty_stdin_exits_zero(tmp_path: Path) -> None:
    """AD-2 2026-09-23-001: hook 오류(빈 입력)가 모든 도구 호출을 막으면 안 된다."""
    _copy_bundle(tmp_path)

    result = _run(tmp_path, "")

    assert result.returncode == 0, result.stdout + result.stderr
