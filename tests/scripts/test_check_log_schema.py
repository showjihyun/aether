"""AD-2 후보: verify 의 `log-schema` 단계가 improvement-log 예시·로그 49건을 매 실행마다
전수 검사해 57초가 걸린다(건당 ~1.1초, 거의 전부 프로세스 생성 비용). improvement-log 는
append-only 이므로 이미 검증을 통과한 파일을 매번 다시 볼 이유가 없다.

이 테스트는 `scripts/check-log-schema.sh` 가 다음을 만족하는지 검증한다.

- 로컬(CI 미설정): 기준선(origin/main 이 있으면 merge-base, 없으면 HEAD) 대비 바뀐
  improvement-log/*.yaml 만 검사하고, 바뀌지 않은 잘못된 파일은 걸러내지 못한다(이
  설계의 트레이드오프 — 속도를 위해 과거 파일의 재검증을 포기한다).
- 로컬: 바뀐 것이 없으면 정본 예시(harness/improvement-log/2026-08-09-001.example.yaml)
  만 검사한다. 그 예시가 없으면(번들에서 지워졌다는 뜻) 검사 대상 0건은 통과가 아니라
  실패다.
- `CI=1`: 번들 예시 + 프로젝트 로그 전수를 검사한다(기존 self-check.sh --only
  log-schema 와 동일 범위) — 바뀌지 않은 잘못된 파일도 잡아낸다.

임시 git 저장소(`git init` + 커밋 1개)를 만들고, 그 안에 진짜 저장소의
`harness/scripts/improvement-log.sh`·`harness/scripts/lib/common.sh`·정본 예시 파일을
복사해 검증기를 실제로 동작시킨다. 소켓을 열지 않고 subprocess 로 bash 스크립트만
실행하므로 `pytest-socket` 기본 `--disable-socket` 아래에서도 돈다.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "scripts" / "check-log-schema.sh"

# Windows 의 CreateProcess 가 인자 하나짜리 "bash" 를 System32 의 WSL 런처로 오인하는
# 문제를 피하기 위해 Git Bash 의 절대경로를 찾습니다(test_check_bench.py 와 동일 관례).
_BASH = shutil.which("bash") or "bash"
_GIT = shutil.which("git") or "git"

VALID_YAML = """id: 2026-09-24-001
date: 2026-09-24
status: candidate
symptom: 테스트용 증상입니다.
evidence: |
  테스트용 근거입니다.
root_cause: 테스트용 원인입니다.
fix: 테스트용 조치입니다.
recurrence_risk: low
harness_element: HE-4
proposed_harness_change: 테스트용 제안입니다.
preferred_enforcement: test
trust: untrusted
regression_check: 테스트용 회귀 확인입니다.
owner: unassigned
expires: none
"""

INVALID_YAML = """id: not-a-valid-id
date: 2026-09-24
status: candidate
"""


def _run_git(root: Path, *args: str) -> None:
    subprocess.run(
        [_GIT, "-C", str(root), *args],
        check=True,
        capture_output=True,
        text=True,
    )


def _setup_repo(root: Path) -> None:
    """진짜 저장소의 validator·정본 예시를 복사한 최소 git 저장소를 만듭니다."""
    (root / "harness" / "scripts" / "lib").mkdir(parents=True)
    (root / "harness" / "improvement-log").mkdir(parents=True)
    (root / "improvement-log").mkdir(parents=True)

    shutil.copy(
        REPO_ROOT / "harness" / "scripts" / "improvement-log.sh",
        root / "harness" / "scripts" / "improvement-log.sh",
    )
    shutil.copy(
        REPO_ROOT / "harness" / "scripts" / "lib" / "common.sh",
        root / "harness" / "scripts" / "lib" / "common.sh",
    )
    shutil.copy(
        REPO_ROOT / "harness" / "improvement-log" / "2026-08-09-001.example.yaml",
        root / "harness" / "improvement-log" / "2026-08-09-001.example.yaml",
    )

    _run_git(root, "init", "-q")
    _run_git(root, "config", "user.email", "test@example.com")
    _run_git(root, "config", "user.name", "Test")
    _run_git(root, "add", "-A")
    _run_git(root, "commit", "-q", "-m", "initial")


def _run(root: Path, *, ci: bool = False) -> subprocess.CompletedProcess[str]:
    env: dict[str, str] = {}
    import os

    env.update(os.environ)
    if ci:
        env["CI"] = "1"
    else:
        env.pop("CI", None)
    return subprocess.run(
        [_BASH, str(SCRIPT_PATH), "--root", str(root)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        env=env,
    )


def _last_line(output: str) -> str:
    stripped = output.strip()
    return stripped.splitlines()[-1] if stripped else ""


def test_local_changed_invalid_log_fails(tmp_path: Path) -> None:
    """로컬 모드: 바뀐(커밋되지 않은) improvement-log/*.yaml 이 스키마를 어기면 실패한다."""
    _setup_repo(tmp_path)
    (tmp_path / "improvement-log" / "2026-09-24-001.yaml").write_text(
        INVALID_YAML, encoding="utf-8"
    )

    result = _run(tmp_path, ci=False)

    assert result.returncode == 1, result.stdout + result.stderr
    assert "실패" in _last_line(result.stdout), result.stdout


def test_local_changed_valid_log_passes(tmp_path: Path) -> None:
    """로컬 모드: 바뀐 improvement-log/*.yaml 이 스키마를 만족하면 통과한다."""
    _setup_repo(tmp_path)
    (tmp_path / "improvement-log" / "2026-09-24-001.yaml").write_text(VALID_YAML, encoding="utf-8")

    result = _run(tmp_path, ci=False)

    assert result.returncode == 0, result.stdout + result.stderr
    last_line = _last_line(result.stdout)
    assert "통과" in last_line, last_line
    assert "변경 1건" in last_line, last_line


def test_local_no_changes_checks_canonical_example_only(tmp_path: Path) -> None:
    """로컬 모드: 바뀐 것이 없으면 정본 예시만 검사한다.

    이 설계의 트레이드오프: 커밋된(바뀌지 않은) 잘못된 로그 파일이 있어도 이 모드는
    그것을 잡지 못하고 통과한다 — 속도를 위해 과거 파일의 재검증을 포기했기 때문이다.
    이 트레이드오프는 CI 전수 검사(`CI=1`)가 메운다.
    """
    _setup_repo(tmp_path)
    # 커밋된 잘못된 파일 — "바뀐 것" 이 아니므로 로컬 모드는 이것을 보지 않는다.
    (tmp_path / "improvement-log" / "2026-09-01-001.yaml").write_text(
        INVALID_YAML, encoding="utf-8"
    )
    _run_git(tmp_path, "add", "-A")
    _run_git(tmp_path, "commit", "-q", "-m", "add invalid but already-committed log")

    result = _run(tmp_path, ci=False)

    assert result.returncode == 0, result.stdout + result.stderr
    last_line = _last_line(result.stdout)
    assert "통과" in last_line, last_line
    assert "정본 예시" in last_line, last_line


def test_local_missing_canonical_example_fails(tmp_path: Path) -> None:
    """로컬 모드: 바뀐 것도 없고 정본 예시도 없으면(번들에서 지워졌다는 뜻) 실패한다.

    검사 대상 0건은 통과가 아니다 — 게이트를 지우는 것이 게이트를 초록으로 만드는
    방법이 되는 것을 막는다.
    """
    _setup_repo(tmp_path)
    canonical = tmp_path / "harness" / "improvement-log" / "2026-08-09-001.example.yaml"
    canonical.unlink()
    _run_git(tmp_path, "add", "-A")
    _run_git(tmp_path, "commit", "-q", "-m", "remove canonical example")

    result = _run(tmp_path, ci=False)

    assert result.returncode == 1, result.stdout + result.stderr
    assert "실패" in _last_line(result.stdout), result.stdout


def test_ci_full_scan_catches_uncommitted_and_committed_invalid_files(
    tmp_path: Path,
) -> None:
    """`CI=1`: 바뀌지 않은(커밋된) 잘못된 파일도 전수 검사에 걸려 실패한다."""
    _setup_repo(tmp_path)
    (tmp_path / "improvement-log" / "2026-09-01-001.yaml").write_text(
        INVALID_YAML, encoding="utf-8"
    )
    _run_git(tmp_path, "add", "-A")
    _run_git(tmp_path, "commit", "-q", "-m", "add invalid but already-committed log")

    result = _run(tmp_path, ci=True)

    assert result.returncode == 1, result.stdout + result.stderr
    last_line = _last_line(result.stdout)
    assert "실패" in last_line, last_line
    assert "CI 전수" in last_line, last_line


def test_ci_full_scan_all_valid_passes(tmp_path: Path) -> None:
    """`CI=1`: 프로젝트 로그와 번들 예시가 전부 올바르면 통과한다."""
    _setup_repo(tmp_path)
    (tmp_path / "improvement-log" / "2026-09-24-001.yaml").write_text(VALID_YAML, encoding="utf-8")

    result = _run(tmp_path, ci=True)

    assert result.returncode == 0, result.stdout + result.stderr
    last_line = _last_line(result.stdout)
    assert "통과" in last_line, last_line
    assert "CI 전수" in last_line, last_line
