"""`e2e` 단계가 **판정에 실제로 걸려 있는가**(plan 0006 H-2b).

MVP-3(PR #168)이 `scripts/e2e.sh` 에 단언 셋(R-9·C-5·R-8)을 넣었지만, 그 스크립트는
`harness.config` 의 `HARNESS_STEPS` 에 등록되기 전까지 **아무 게이트도 지키지 않는다** —
사람이 손으로 부를 때만 돈다. 이 테스트가 고정하는 것은 그 배선이다.

왜 스크립트 쪽 테스트(`test_e2e_script.py`)로 충분하지 않은가: 그것은 스크립트가
무엇을 단언하는지를 보고, 이것은 **누가 그 스크립트를 부르는지**를 본다. 등록이
빠지면 전자는 전부 통과한 채로 CI 에서 e2e 가 한 번도 돌지 않는다.

함께 보는 것 둘:

  - **미룸 목록에 있는가.** 없으면 로컬 기본 실행이 112초 늘고(실측), 단위마다 Docker
    스택을 다시 띄운다 — 사람 결정 2026-10-11(미룸)의 이유가 그대로 깨진다. CI 는
    `--full` 이므로 미뤄도 게이트는 약해지지 않는다(`test_verify_deferred.py`).
  - **등록한 명령이 실행 가능한가.** 2026-10-18 에 CI(Linux)가 `Permission denied` 로
    잡은 그 부류다(`improvement-log/2026-10-18-002.yaml`). 등록 줄의 경로를 그대로
    읽어 git 인덱스 모드를 본다 — `test_script_exec_bits.py` 는 `scripts/*.sh` 전부를
    보고, 여기서는 **이 단계가 부르는 바로 그 파일**을 본다.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

# Windows 의 CreateProcess 는 인자 하나짜리 "bash" 를 System32 의 WSL 런처로 잡습니다
# (test_verify_deferred.py 와 같은 이유로 절대 경로를 씁니다).
_BASH = shutil.which("bash") or "bash"

STEP_ID = "e2e"


def _steps() -> tuple[list[str], list[str]]:
    """실제 `harness.config` 를 bash 로 source 해서 단계 줄과 미룸 목록을 읽는다.

    정규식으로 파일을 긁지 않는다 — 배열 리터럴을 직접 파싱하면 주석·따옴표·줄바꿈을
    bash 와 다르게 읽을 수 있고, 그러면 테스트가 보는 설정과 verify.sh 가 보는 설정이
    갈라진다.
    """
    script = f"""
set -euo pipefail
source "{(REPO_ROOT / "harness.config").as_posix()}"
printf '%s\n' "${{HARNESS_STEPS[@]}}"
printf -- '---\n'
printf '%s\n' "${{HARNESS_DEFERRED_STEPS[*]-}}"
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
    head, _, tail = out.partition("---\n")
    return [line for line in head.splitlines() if line.strip()], tail.split()


def test_e2e_is_a_registered_required_step() -> None:
    """등록되어 있고 `required=true` 이며 `scripts/e2e.sh` 를 부른다."""
    steps, _ = _steps()
    matching = [line for line in steps if line.split("|", 1)[0] == STEP_ID]

    assert matching, (
        f"harness.config 의 HARNESS_STEPS 에 `{STEP_ID}` 가 없습니다 — scripts/e2e.sh 가 "
        "어느 게이트에서도 돌지 않습니다"
    )
    assert len(matching) == 1, matching
    step_id, layer, required, command = matching[0].split("|", 3)
    assert layer == "behavior", layer
    assert required == "true", (
        f"`{step_id}` 가 required=false 입니다 — 실패해도 병합이 막히지 않습니다"
    )
    assert command.strip() == "scripts/e2e.sh", command


def test_e2e_is_deferred_in_the_local_default() -> None:
    """로컬 기본 실행에는 들어가지 않는다(실측 112초). CI 는 `--full` 로 돌린다."""
    _, deferred = _steps()

    assert STEP_ID in deferred, (
        f"`{STEP_ID}` 가 HARNESS_DEFERRED_STEPS 에 없습니다 — 로컬 기본 실행마다 Docker "
        "스택을 다시 띄우며 약 112초가 더 듭니다"
    )


def test_the_command_the_step_runs_is_executable_in_git() -> None:
    """등록 줄이 가리키는 파일의 git 모드가 100755 인가.

    Windows 에서 만든 파일은 100644 로 커밋되고, 그러면 리눅스 CI 에서만
    `Permission denied` 가 난다(2026-10-18 실측, improvement-log/2026-10-18-002).
    """
    steps, _ = _steps()
    matching = [line for line in steps if line.split("|", 1)[0] == STEP_ID]
    assert matching, f"`{STEP_ID}` 단계가 없습니다"
    command = matching[0].split("|", 3)[3].strip()

    out = subprocess.run(
        ["git", "ls-files", "-s", "--", command],
        cwd=REPO_ROOT,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        check=True,
        timeout=60,
    ).stdout.strip()

    assert out, f"{command} 가 git 에 없습니다 — 등록한 명령이 저장소에 없습니다"
    mode = out.split()[0]
    assert mode == "100755", (
        f"{command} 의 git 모드가 {mode} 입니다. 리눅스 CI 에서 Permission denied 로 "
        f"죽습니다 — `git update-index --chmod=+x {command}` 로 고칩니다"
    )
