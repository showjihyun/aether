"""`harness/scripts/verify.sh` 의 단일 실행 락.

근거: improvement-log `2026-10-03-001`. 2026-10-03 에 주 세션과 위임 세션이 verify 를
동시에 돌려 `.harness/verify.json` 에 JSON 문서 두 개가 이어 붙었고(파싱 불가) 한쪽
실행이 엉뚱한 필수 실패로 끝났다. 락이 없으면 같은 Docker 자원(compose 프로젝트·호스트
포트)과 같은 결과 파일을 두 실행이 함께 쓴다.

여기서 고정하는 것은 **점유 중이면 기다리지 않고 비영 종료한다**는 것뿐이다. 기다리면 두
실행이 Docker 를 교대로 잡는 더 나쁜 상태가 된다. 예산 판정과 절전 의심 표시는 전량
실행이 필요해 이 테스트의 대상이 아니다(PR 본문에 실측을 남긴다).
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
VERIFY = REPO_ROOT / "harness" / "scripts" / "verify.sh"
# Windows 의 CreateProcess 는 인자 하나짜리 "bash" 를 System32 의 WSL 런처로 잡습니다
# (tests/scripts/test_guard_protected.py 와 같은 이유로 절대 경로를 씁니다).
_BASH = shutil.which("bash") or "bash"
# 이 테스트는 api-unit 단계 안에서, 즉 바깥 verify 가 락을 잡은 동안 돈다. 그래서
# HARNESS_VERIFY_LOCK_DIR 로 테스트 전용 락 경로를 주어 바깥 실행의 락을 건드리지 않는다.
LOCK_DIR_ENV = "HARNESS_VERIFY_LOCK_DIR"
LOCK_EXIT_CODE = 4


def _run_verify(
    lock_dir: Path, *args: str, env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    merged = dict(os.environ)
    merged["TESTCONTAINERS_RYUK_DISABLED"] = "true"
    merged[LOCK_DIR_ENV] = str(lock_dir)
    if env:
        merged.update(env)
    return subprocess.run(
        [_BASH, str(VERIFY), *args],
        cwd=REPO_ROOT,
        capture_output=True,
        # text=True 만 주면 Windows 기본 코드페이지(cp949)로 디코딩하다 한국어 출력에서
        # UnicodeDecodeError 가 나고, 리더 스레드가 죽어 stdout·stderr 가 None 이 된다.
        encoding="utf-8",
        errors="replace",
        env=merged,
        timeout=600,
    )


@pytest.fixture
def lock_dir(tmp_path: Path) -> Path:
    """이 테스트만의 락 경로."""
    return tmp_path / "verify.lock"


@pytest.fixture
def held_lock(lock_dir: Path) -> Path:
    """다른 verify 가 점유한 상태를 만든다."""
    lock_dir.mkdir(parents=True)
    (lock_dir / "owner").write_text("pid=test\nstarted_at=test\n", encoding="utf-8")
    return lock_dir


def test_second_run_exits_without_waiting_while_the_lock_is_held(held_lock: Path) -> None:
    """락이 잡혀 있으면 단계를 하나도 돌리지 않고 종료 코드 4 로 끝난다."""
    result = _run_verify(held_lock, "--only", "syntax")

    assert result.returncode == LOCK_EXIT_CODE, result.stdout + result.stderr
    assert "다른 verify 가 실행 중입니다" in result.stderr
    # 소유자를 보여 주어야 사람이 무엇이 잡고 있는지 알 수 있다.
    assert "pid=test" in result.stderr


def test_stale_lock_is_reclaimed(held_lock: Path) -> None:
    """나이가 임계를 넘은 락은 회수한다 — 비정상 종료가 다음 실행을 영구히 막지 않게."""
    result = _run_verify(held_lock, "--only", "syntax", env={"HARNESS_VERIFY_LOCK_STALE_S": "0"})

    assert result.returncode == 0, result.stdout + result.stderr
    assert "오래된 verify 락을 회수했습니다" in result.stderr


def test_lock_is_released_after_a_normal_run(lock_dir: Path) -> None:
    """정상 종료 뒤에는 락이 남지 않는다(trap)."""
    assert not lock_dir.exists(), "이 테스트는 락이 없는 상태에서 시작한다"
    result = _run_verify(lock_dir, "--only", "syntax")

    assert result.returncode == 0, result.stdout + result.stderr
    assert not lock_dir.exists()
