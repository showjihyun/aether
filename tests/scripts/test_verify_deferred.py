"""로컬 기본에서 미루는 단계(`HARNESS_DEFERRED_STEPS`)와 그 미룸이 게이트를 약하게
만들지 않는다는 조건.

사람 결정(showjihyun, 2026-10-11): 통합·e2e 단계를 **로컬 기본에서 빼고 CI 필수로는
그대로 둔다.** 근거는 "Phase 별로 테스트하고 어느 정도 기능이 구현되면 그때 연동이나
통합테스트를 하게" 하는 것이다 — 단위마다 전량(약 400~470초)을 다시 돌리는 것이 느려
에이전트가 일을 못 한다.

이 변경은 **로컬 완료 근거를 의도적으로 약화시킨다.** 그래서 무엇이 약해지고 무엇이
약해지지 않는지를 여기서 못 박는다.

  약해지는 것   로컬 `verify.sh` 의 완료 판정. 미룬 단계는 돌지 않았으므로 통과한 것이
                아니고, Stop 게이트도 그것을 "전량 통과" 로 적지 않는다(부분 실행으로
                기록되고 미룬 단계 이름이 출력된다).
  약해지지 않는 것
                병합 게이트. CI 는 `--full` 로 전량을 돌리고 그 단계들은 `required=true`
                그대로다. `required` 를 내리거나 단계를 지우는 방식은 쓰지 않는다 —
                그것은 수정이 아니다(AGENTS.md Verification 3).

`--only` 부분 실행이 여전히 차단된다는 것도 함께 고정한다. 그것이 풀리면 "한 단계만
돌린 pass" 와 "미룬 단계만 안 돈 pass" 가 구별되지 않는다.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
CI_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "harness.yml"
HARNESS_CONFIG = REPO_ROOT / "harness.config"

# Windows 의 CreateProcess 는 인자 하나짜리 "bash" 를 System32 의 WSL 런처로 잡습니다
# (tests/scripts/test_verify_lock.py 와 같은 이유로 절대 경로를 씁니다).
_BASH = shutil.which("bash") or "bash"

FAST_STEPS = ("fast-a", "fast-b")
DEFERRED_STEPS = ("heavy-int", "heavy-smoke")

_SANDBOX_CONFIG = """# 테스트용 샌드박스 설정입니다. 단계 명령은 전부 `true` 로 두어
# 이 테스트가 재는 것이 **범위 판정**이지 단계의 내용이 아니게 합니다.
HARNESS_SCOPE_DOC_PATTERNS=("*.md")
HARNESS_SCOPE_DOC_STEPS=(fast-a)
HARNESS_STEPS=(
  "fast-a|correctness|true|true"
  "fast-b|quality|true|true"
  "heavy-int|correctness|true|true"
  "heavy-smoke|behavior|true|true"
)
HARNESS_DEFERRED_STEPS=(heavy-int heavy-smoke)
HARNESS_THRESHOLD=80
"""


@pytest.fixture
def sandbox(tmp_path: Path) -> Path:
    """자기 harness.config 를 가진 작은 프로젝트. 번들(harness/)은 진짜 파일을 복사한다."""
    root = tmp_path / "project"
    root.mkdir()
    shutil.copytree(REPO_ROOT / "harness", root / "harness")
    (root / "harness.config").write_text(_SANDBOX_CONFIG, encoding="utf-8", newline="\n")
    (root / "README.md").write_text("# sandbox\n", encoding="utf-8", newline="\n")
    return root


def _run_verify(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    # 바깥 verify 가 락을 잡은 동안(api-unit·harness-scripts 단계 안에서) 돌 수 있으므로
    # 테스트 전용 락 경로를 준다(test_verify_lock.py 와 같은 이유).
    env["HARNESS_VERIFY_LOCK_DIR"] = str(root / ".harness" / "test.lock")
    return subprocess.run(
        [_BASH, str(root / "harness" / "scripts" / "verify.sh"), *args],
        cwd=root,
        capture_output=True,
        # text=True 만 주면 Windows 기본 코드페이지(cp949)로 디코딩하다 한국어 출력에서
        # UnicodeDecodeError 가 난다.
        encoding="utf-8",
        errors="replace",
        env=env,
        timeout=600,
    )


def _verify_json(root: Path) -> dict[str, Any]:
    data = json.loads((root / ".harness" / "verify.json").read_text(encoding="utf-8"))
    assert isinstance(data, dict), data
    return data


def _run_stop_gate(root: Path) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env["CLAUDE_PROJECT_DIR"] = str(root)
    env.pop("HARNESS_SKIP_STOP_GATE", None)
    return subprocess.run(
        [_BASH, str(root / "harness" / "hooks" / "stop-verify-gate.sh")],
        input="{}",
        cwd=root,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        timeout=600,
    )


# --- 범위 판정 ----------------------------------------------------------------------


def test_default_run_defers_the_heavy_steps(sandbox: Path) -> None:
    """옵션 없는 실행은 미룬 단계를 돌리지 않는다."""
    result = _run_verify(sandbox)

    assert result.returncode == 0, result.stdout + result.stderr
    data = _verify_json(sandbox)
    ran = [s["id"] for s in data["steps"]]
    assert ran == list(FAST_STEPS), ran
    assert data["defined_steps"] == 4
    assert data["ran_steps"] == 2
    assert data["partial"] is True, "미룬 실행은 전량 통과로 기록되면 안 된다"
    assert data["deferred"] == list(DEFERRED_STEPS), data.get("deferred")


_DEFER_NOTICE = "로컬 기본에서 미뤘습니다"
"""미룸을 알리는 문구. 단계 이름만 보면 **돌았을 때도** 출력에 있으므로, 이 문구와
함께 봐야 "미뤘다" 와 "돌렸다" 가 구별된다."""


def test_default_run_says_which_steps_it_deferred(sandbox: Path) -> None:
    """콘솔을 보는 사람이 "전량 통과" 로 오해하지 않게 미룬 단계를 이름으로 알린다."""
    result = _run_verify(sandbox)

    out = result.stdout + result.stderr
    assert _DEFER_NOTICE in out, f"미룸을 알리는 문구가 없습니다: {out}"
    for step in DEFERRED_STEPS:
        assert step in out, f"{step} 를 미뤘다는 말이 출력에 없습니다: {out}"
    assert "--full" in out, "전량을 돌리는 방법을 함께 알려야 합니다"


def test_full_runs_every_step(sandbox: Path) -> None:
    """`--full` 은 미룬 단계까지 돌린다 — CI 가 쓰는 경로다."""
    result = _run_verify(sandbox, "--full")

    assert result.returncode == 0, result.stdout + result.stderr
    data = _verify_json(sandbox)
    assert [s["id"] for s in data["steps"]] == list(FAST_STEPS) + list(DEFERRED_STEPS)
    assert data["ran_steps"] == 4
    assert data["partial"] is False
    assert data["deferred"] == []


def test_only_can_still_name_a_deferred_step(sandbox: Path) -> None:
    """명시한 것이 기본보다 강하다 — 미뤘다고 해서 부를 수 없게 되면 안 된다."""
    result = _run_verify(sandbox, "--only", "heavy-int")

    assert result.returncode == 0, result.stdout + result.stderr
    data = _verify_json(sandbox)
    assert [s["id"] for s in data["steps"]] == ["heavy-int"]


def test_a_failing_deferred_step_still_fails_under_full(sandbox: Path) -> None:
    """미룬 단계의 required 는 내려가지 않는다. `--full` 에서 실패하면 전체가 실패다."""
    config = (sandbox / "harness.config").read_text(encoding="utf-8")
    config = config.replace(
        '"heavy-int|correctness|true|true"', '"heavy-int|correctness|true|false"'
    )
    (sandbox / "harness.config").write_text(config, encoding="utf-8", newline="\n")

    result = _run_verify(sandbox, "--full")

    assert result.returncode == 1, result.stdout + result.stderr
    assert _verify_json(sandbox)["status"] == "fail"


# --- Stop 게이트 --------------------------------------------------------------------


def test_stop_gate_accepts_a_run_that_only_deferred(sandbox: Path) -> None:
    """미룬 단계만 안 돈 부분 실행은 완료 근거로 받는다 — 이 변경의 핵심이다.

    이것이 없으면 미룸은 무용하다. 코드를 고칠 때마다 Stop 게이트가 전량을 요구하므로
    로컬 기본을 바꾼 의미가 사라진다.
    """
    assert _run_verify(sandbox).returncode == 0

    result = _run_stop_gate(sandbox)

    assert result.returncode == 0, result.stdout + result.stderr


def test_stop_gate_names_the_deferred_steps_when_it_lets_you_go(sandbox: Path) -> None:
    """통과시키면서도 **무엇이 판정되지 않았는지** 를 말한다. 조용히 통과시키면 그
    부분 실행이 전량 통과처럼 보인다.
    """
    assert _run_verify(sandbox).returncode == 0

    result = _run_stop_gate(sandbox)

    for step in DEFERRED_STEPS:
        assert step in result.stderr, f"{step} 가 게이트 메시지에 없습니다: {result.stderr}"


def test_stop_gate_still_blocks_an_only_partial_run(sandbox: Path) -> None:
    """`--only` 부분 실행은 그대로 차단한다. 이것이 풀리면 미룸 예외가 모든 부분 실행의
    예외가 된다.
    """
    assert _run_verify(sandbox, "--only", "fast-a").returncode == 0

    result = _run_stop_gate(sandbox)

    assert result.returncode == 2, result.stdout + result.stderr
    assert "부분 실행" in result.stderr


# --- 설정과 CI 가 갈라지지 않는가 -----------------------------------------------------


def test_ci_runs_the_full_set() -> None:
    """CI 가 `--full` 로 돌지 않으면 미룬 단계는 **어디서도** 돌지 않는다.

    이 한 줄이 "로컬만 빠르게" 와 "게이트를 약화" 를 가르는 자리다. 환경변수 자동 감지
    대신 워크플로가 명시하게 했다 — 동작이 파일에 보이지 않으면 다음 사람이 읽을 수 없다.
    """
    text = CI_WORKFLOW.read_text(encoding="utf-8")
    assert "verify.sh --full" in text, (
        "CI 워크플로가 verify.sh --full 로 돌지 않습니다 — 미룬 단계가 아무 데서도 "
        "판정되지 않습니다"
    )


def test_every_deferred_id_exists_as_a_step() -> None:
    """미룬 id 에 오타가 있으면 아무것도 미뤄지지 않고(또는 엉뚱한 것이 미뤄지고) 아무
    신호도 나지 않는다. 실제 harness.config 를 읽어 대조한다.
    """
    script = f"""
set -euo pipefail
source "{(REPO_ROOT / "harness.config").as_posix()}"
printf 'steps=%s\\n' "$(printf '%s\\n' "${{HARNESS_STEPS[@]}}" | cut -d'|' -f1 | tr '\\n' ' ')"
printf 'deferred=%s\\n' "${{HARNESS_DEFERRED_STEPS[*]-}}"
"""
    out = subprocess.run(
        [_BASH, "-c", script],
        cwd=REPO_ROOT,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        check=True,
        timeout=60,
    ).stdout
    values = dict(line.split("=", 1) for line in out.strip().splitlines())
    defined = set(values["steps"].split())
    deferred = set(values["deferred"].split())

    assert deferred, "harness.config 에 HARNESS_DEFERRED_STEPS 가 없습니다"
    assert deferred <= defined, f"HARNESS_STEPS 에 없는 id 를 미뤘습니다: {deferred - defined}"
