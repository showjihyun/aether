"""`harness/scripts/lib/common.sh` 의 `harness_scope_fingerprint`.

근거: improvement-log `2026-10-09-001`. 이 함수는 `verify.sh` 가 범위(`--changed`)를
판정하려고 **모든 실행에서 두 번** 부릅니다(docs·code). 2026-10-11 프로파일에서 단계를
하나도 돌리지 않는 실행조차 38.5초가 걸렸고, 간격의 거의 전부가 파일마다 하나씩 띄우는
`git hash-object` 프로세스였습니다 — 추적+비추적 801개 파일에 프로세스 801개입니다.

그래서 여기서 고정하는 것은 **지문 값**과 **프로세스 수** 둘입니다. 값만 고정하면 다시
파일마다 git 을 띄우는 구현으로 되돌아가도 테스트가 통과하고, 프로세스 수만 고정하면
값이 달라져도 통과합니다. 비용을 줄이는 변경에서 정작 지켜야 하는 것은 값입니다.

바로 윗형제인 `harness_tree_fingerprint` 는 index 를 뼈대로 써서 더러운 파일만
해시합니다. `harness_scope_fingerprint` 의 주석도 "index 를 뼈대로 쓰고" 라고 적고
있는데 구현은 그렇지 않았습니다 — 주석이 코드보다 앞서 있던 자리입니다.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
COMMON_SH = REPO_ROOT / "harness" / "scripts" / "lib" / "common.sh"
# Windows 의 CreateProcess 는 인자 하나짜리 "bash" 를 System32 의 WSL 런처로 잡습니다
# (tests/scripts/test_verify_lock.py 와 같은 이유로 절대 경로를 씁니다).
_BASH = shutil.which("bash") or "bash"
_GIT = shutil.which("git") or "git"

_FILE_COUNT = 24
"""지문이 **파일 수에 비례해** git 을 띄우는지 보려면 파일이 여럿이어야 합니다. 24개면
고친 뒤(모드당 1회)와 고치기 전(모드당 24회)이 한눈에 갈립니다."""


def _bash(
    script: str, cwd: Path, env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    merged = dict(os.environ)
    if env:
        merged.update(env)
    return subprocess.run(
        [_BASH, "-c", script],
        cwd=cwd,
        capture_output=True,
        # text=True 만 주면 Windows 기본 코드페이지(cp949)로 디코딩하다 한국어 출력에서
        # UnicodeDecodeError 가 납니다(tests/scripts/test_verify_lock.py 와 같은 이유).
        encoding="utf-8",
        errors="replace",
        env=merged,
        timeout=600,
    )


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        [_GIT, "-C", str(repo), *args],
        check=True,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
    )


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """추적 파일과 비추적 파일이 섞인 작은 git 저장소."""
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "test@example.com")
    _git(root, "config", "user.name", "test")
    for index in range(_FILE_COUNT):
        suffix = "md" if index % 3 == 0 else "py"
        (root / f"file{index:02d}.{suffix}").write_text(f"content {index}\n", encoding="utf-8")
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "seed")
    # 비추적 파일도 지문의 입력입니다(`--others --exclude-standard`).
    (root / "untracked.py").write_text("new\n", encoding="utf-8")
    return root


def _fingerprint_script(want: str, *, doc_patterns: str = "'*.md'") -> str:
    # Windows 경로를 그대로 넣으면 bash 가 역슬래시를 이스케이프로 먹습니다
    # (`C:WorkSpaceaether…` 로 뭉개집니다, 실측). `as_posix()` 로 넘깁니다.
    return f"""
set -euo pipefail
source "{COMMON_SH.as_posix()}"
HARNESS_SCOPE_DOC_PATTERNS=({doc_patterns})
harness_scope_fingerprint "$PWD" {want}
"""


def _fingerprint(repo: Path, want: str, **kwargs: str) -> str:
    result = _bash(_fingerprint_script(want, **kwargs), repo)
    assert result.returncode == 0, result.stdout + result.stderr
    value = result.stdout.strip()
    assert value, f"지문이 비어 있습니다: {result.stdout + result.stderr}"
    return value


# --- 값 ----------------------------------------------------------------------


def test_same_tree_gives_the_same_fingerprint(repo: Path) -> None:
    """같은 작업 트리는 같은 값입니다 — 범위 비교가 이 성질 위에 있습니다."""
    assert _fingerprint(repo, "code") == _fingerprint(repo, "code")


def test_editing_a_code_file_changes_the_code_fingerprint(repo: Path) -> None:
    before = _fingerprint(repo, "code")
    (repo / "file01.py").write_text("changed\n", encoding="utf-8")
    assert _fingerprint(repo, "code") != before


def test_editing_a_doc_file_leaves_the_code_fingerprint_alone(repo: Path) -> None:
    """`--changed` 가 문서만 고친 커밋에서 코드 단계를 건너뛰는 근거입니다."""
    before = _fingerprint(repo, "code")
    (repo / "file00.md").write_text("doc changed\n", encoding="utf-8")
    assert _fingerprint(repo, "code") == before


def test_editing_a_doc_file_changes_the_doc_fingerprint(repo: Path) -> None:
    """반대 확인 — 문서 지문이 문서 변경에 무감각하면 위 테스트가 공허해집니다."""
    before = _fingerprint(repo, "docs")
    (repo / "file00.md").write_text("doc changed\n", encoding="utf-8")
    assert _fingerprint(repo, "docs") != before


def test_committing_does_not_change_the_fingerprint(repo: Path) -> None:
    """커밋 불변 — improvement-log 2026-09-05-003 이 같은 함정을 이미 한 번 잡았습니다."""
    (repo / "file01.py").write_text("changed\n", encoding="utf-8")
    before = _fingerprint(repo, "code")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "change")
    assert _fingerprint(repo, "code") == before


def test_untracked_files_are_part_of_the_fingerprint(repo: Path) -> None:
    before = _fingerprint(repo, "code")
    (repo / "untracked.py").write_text("new content\n", encoding="utf-8")
    assert _fingerprint(repo, "code") != before


# --- 프로세스 수 --------------------------------------------------------------


def _git_shim(log: Path) -> Path:
    """인자를 기록하고 진짜 git 으로 넘기는 래퍼. PATH 앞에 놓습니다."""
    shim_dir = log.parent / "shim"
    shim_dir.mkdir(parents=True, exist_ok=True)
    script = shim_dir / "git"
    # 두 경로 모두 공백이 있는 Windows 경로일 수 있으므로 POSIX 표기 + 인용입니다
    # (`exec C:\\Program Files\\…\\git.exe` 는 공백에서 갈라져 조용히 실패합니다, 실측).
    script.write_text(
        "#!/usr/bin/env bash\n"
        f'printf \'%s\\n\' "$*" >> "{log.as_posix()}"\n'
        f'exec "{Path(_GIT).as_posix()}" "$@"\n',
        encoding="utf-8",
        newline="\n",
    )
    script.chmod(0o755)
    return shim_dir


def _hash_object_calls(repo: Path, want: str) -> int:
    log = repo.parent / "git-calls.log"
    if log.exists():
        log.unlink()
    shim_dir = _git_shim(log)
    result = _bash(
        _fingerprint_script(want),
        repo,
        env={"PATH": f"{shim_dir.as_posix()}{os.pathsep}{os.environ.get('PATH', '')}"},
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.strip(), "지문이 비어 있으면 호출 수 단언이 공허합니다"
    if not log.exists():
        pytest.fail("shim 이 한 번도 불리지 않았습니다 — PATH 주입이 듣지 않았습니다")
    lines = log.read_text(encoding="utf-8").splitlines()
    assert any("ls-files" in line for line in lines), (
        f"ls-files 호출이 기록되지 않았습니다 — shim 이 실제로 쓰이는지 의심스럽습니다: {lines[:5]}"
    )
    return sum(1 for line in lines if "hash-object" in line)


@pytest.mark.parametrize("want", ["code", "docs"])
def test_fingerprint_spawns_at_most_one_hash_object_process(repo: Path, want: str) -> None:
    """지문 한 벌이 띄우는 `git hash-object` 프로세스는 **파일 수와 무관**해야 합니다.

    2026-10-11 실측: 파일마다 하나씩 띄우던 구현은 801개 파일에서 38.5초를 썼고, 그
    비용은 단계를 하나도 돌리지 않는 실행에도 들었습니다. 같은 입력을 한 번에 넘기면
    값은 그대로이고 소요는 1초 미만입니다(후보 2026-10-09-001).
    """
    calls = _hash_object_calls(repo, want)
    assert calls <= 1, (
        f"{_FILE_COUNT}개 파일짜리 저장소에서 hash-object 를 {calls}번 띄웠습니다. "
        "파일마다 프로세스를 띄우면 비용이 파일 수에 비례합니다"
    )
