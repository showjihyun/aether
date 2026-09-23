"""improvement-log 2026-09-17-001, 2026-09-22-001: `scripts/guard-eval-blind.sh` 가 PreToolUse
hook 으로서 평가 실행(대표 task) 동안 판정 근거가 새는 경로를 막는지 검증한다.

기준선(evaluation/runs/2026-09-17-REP-5.md, 2026-09-17-REP-8-r2.md)에서 실행 에이전트가
task 정의와 지난 판정 기록을 스스로 열어 blind 조건이 깨졌다. 2026-09-21 REP-4 6차 실행에서는
루트 `evaluation/README.md` 와 `improvement-log/` 의 기존 후보(합격 기준·관측 방법이 복제되어
있음)를 읽어 같은 문제가 다시 벌어졌다(2026-09-22-001). 이 hook 은 저장소 루트의 마커 파일
`.eval-blind` 가 있을 때만 두 범주 — 루트 `evaluation/` 전체(harness/evaluation·
packages/evaluation 제외)와 루트 `improvement-log/` 의 마커 이전 항목(harness/improvement-log
제외, 마커 뒤에 새로 생긴 후보 파일과 `improvement-log.sh new`·`validate` 는 허용) — 를
차단한다. 이 테스트는 임시 디렉터리를 `--root` 로 넘기고 hook JSON 을 stdin 으로 흘려 보내
subprocess 로 검사한다 — 자체적으로 소켓을 열지 않으므로 `--disable-socket` 아래에서도
(그리고 `integration` 마크 없이) 돈다.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "scripts" / "guard-eval-blind.sh"

# Windows 의 CreateProcess 는 인자 하나짜리 "bash" 를 넘기면 System32 의 WSL 런처를
# 먼저 찾아 실패한다(실측, aether-windows-pitfalls). shutil.which 로 Git Bash 의
# 절대경로를 찾아 argv[0] 로 명시한다(tests/scripts/test_check_bench.py 와 같은 방식).
_BASH = shutil.which("bash") or "bash"

# 결정적인 마커·파일 수정 시각. sleep 대신 os.utime 으로 명시한다.
_MARKER_EPOCH = 1_700_000_000
_PRE_MARKER_EPOCH = _MARKER_EPOCH - 100
_POST_MARKER_EPOCH = _MARKER_EPOCH + 100


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


def _touch_marker(root: Path, epoch: float = _MARKER_EPOCH) -> Path:
    marker = root / ".eval-blind"
    marker.touch()
    os.utime(marker, (epoch, epoch))
    return marker


def _touch_with_mtime(path: Path, epoch: float) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.touch()
    os.utime(path, (epoch, epoch))


def test_no_marker_allows_reading_task_definition(tmp_path: Path) -> None:
    """improvement-log 2026-09-17-001: 마커가 없으면 평상시 작업이므로 아무것도 막지 않는다."""
    payload = _payload("Read", {"file_path": "evaluation/tasks/representative.md"})

    result = _run(tmp_path, payload)

    assert result.returncode == 0, result.stdout + result.stderr


def test_marker_blocks_reading_representative_task(tmp_path: Path) -> None:
    """improvement-log 2026-09-17-001: 마커가 있으면 representative.md 를 여는 Read 를 막고
    stderr 에 그 경로를 밝힌다 — REP-5 가 스스로 열어 읽은 바로 그 파일이다.
    """
    _touch_marker(tmp_path)
    payload = _payload("Read", {"file_path": "evaluation/tasks/representative.md"})

    result = _run(tmp_path, payload)

    assert result.returncode == 2, result.stdout + result.stderr
    assert "evaluation/tasks/representative.md" in result.stderr


def test_marker_blocks_bash_reading_run_log(tmp_path: Path) -> None:
    """improvement-log 2026-09-17-001: evaluation/runs 는 지난 판정 근거와 평가자가 심은
    결함까지 담고 있어 더 직접적인 누출 경로다. 셸 명령으로 읽는 것도 막는다.
    """
    _touch_marker(tmp_path)
    payload = _payload("Bash", {"command": "cat evaluation/runs/2026-09-17-REP-1.md"})

    result = _run(tmp_path, payload)

    assert result.returncode == 2, result.stdout + result.stderr


def test_marker_blocks_backslash_path(tmp_path: Path) -> None:
    """improvement-log 2026-09-17-001: Windows 경로는 역슬래시로 올 수 있어 두 표기 모두
    잡아야 한다(harness/hooks/guard-evaluation-tampering.sh 의 json_unescape 근거와 같은 결).
    """
    _touch_marker(tmp_path)
    # 실제 문자열 값은 "evaluation\tasks\representative.md" (단일 백슬래시 두 곳)이며,
    # json.dumps 가 JSON 표기에 맞게 이스케이프한다.
    file_path = "evaluation\\tasks\\representative.md"
    payload = _payload("Read", {"file_path": file_path})

    result = _run(tmp_path, payload)

    assert result.returncode == 2, result.stdout + result.stderr


def test_marker_blocks_reading_evaluation_readme(tmp_path: Path) -> None:
    """improvement-log 2026-09-22-001: 2026-09-21 REP-4 6차 실행에서 evaluation/README.md
    (task ID 와 판정 요약을 담고 있음)를 읽어 blind 조건이 partial 로 무효화됐다. 이제는
    evaluation/tasks·evaluation/runs 뿐 아니라 루트 evaluation/ 전체를 막는다.

    이전 이름은 test_marker_allows_reading_readme 였고 evaluation/tasks·evaluation/runs
    밖의 evaluation/ 경로는 막지 않는다고 기대했다. 2026-09-22-001 적용으로 그 기대가
    뒤집혀 이름과 단언을 함께 바꾼다(README.md 도 이제 차단 대상).
    """
    _touch_marker(tmp_path)
    payload = _payload("Read", {"file_path": "evaluation/README.md"})

    result = _run(tmp_path, payload)

    assert result.returncode == 2, result.stdout + result.stderr


def test_marker_allows_unrelated_bash_command(tmp_path: Path) -> None:
    """improvement-log 2026-09-17-001: 마커가 있어도 평가 경로와 무관한 명령은 막지 않는다."""
    _touch_marker(tmp_path)
    payload = _payload("Bash", {"command": "ls apps"})

    result = _run(tmp_path, payload)

    assert result.returncode == 0, result.stdout + result.stderr


def test_block_appends_single_log_line_with_tool_name(tmp_path: Path) -> None:
    """improvement-log 2026-09-17-001: 차단마다 `.eval-blind.log` 에 한 줄을 남겨야
    blind 조건이 실제로 작동했다는 증거가 된다(regression_check 근거).
    """
    _touch_marker(tmp_path)
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
    _touch_marker(tmp_path)

    result = _run(tmp_path, "")

    assert result.returncode == 0, result.stdout + result.stderr


# --- 2026-09-22-001: evaluation/ 전체와 improvement-log/ 기존 항목으로 범위 확장 ---


def test_marker_blocks_bash_grep_evaluation_dir(tmp_path: Path) -> None:
    """2026-09-22-001: 셸 명령으로 evaluation/ 디렉터리 전체를 훑는 것도 막는다."""
    _touch_marker(tmp_path)
    payload = _payload("Bash", {"command": "grep -rn foo evaluation/"})

    result = _run(tmp_path, payload)

    assert result.returncode == 2, result.stdout + result.stderr


def test_marker_allows_reading_harness_evaluation(tmp_path: Path) -> None:
    """2026-09-22-001: harness/evaluation/ 은 번들의 rubric·템플릿이라 막지 않는다."""
    _touch_marker(tmp_path)
    payload = _payload("Read", {"file_path": "harness/evaluation/rubric.md"})

    result = _run(tmp_path, payload)

    assert result.returncode == 0, result.stdout + result.stderr


def test_marker_allows_reading_packages_evaluation(tmp_path: Path) -> None:
    """2026-09-22-001: packages/evaluation/ 은 제품 패키지라 막지 않는다."""
    _touch_marker(tmp_path)
    payload = _payload("Read", {"file_path": "packages/evaluation/src/x.py"})

    result = _run(tmp_path, payload)

    assert result.returncode == 0, result.stdout + result.stderr


def test_marker_blocks_reading_pre_marker_improvement_log_entry(tmp_path: Path) -> None:
    """2026-09-22-001: 마커보다 먼저 있던 improvement-log/ 항목은 합격 기준·관측 방법이
    복제되어 있을 수 있어 읽기를 막는다(REP-4 6차 실행의 2026-09-20-004.yaml 사례).
    """
    _touch_marker(tmp_path)
    _touch_with_mtime(tmp_path / "improvement-log" / "2026-09-20-004.yaml", _PRE_MARKER_EPOCH)
    payload = _payload("Read", {"file_path": "improvement-log/2026-09-20-004.yaml"})

    result = _run(tmp_path, payload)

    assert result.returncode == 2, result.stdout + result.stderr


def test_marker_blocks_bash_grep_improvement_log_dir(tmp_path: Path) -> None:
    """2026-09-22-001: 디렉터리 단위로 improvement-log/ 를 훑는 명령은 마커 뒤에 생긴
    파일만 걸러낼 수 없으므로 막는다.
    """
    _touch_marker(tmp_path)
    _touch_with_mtime(tmp_path / "improvement-log" / "2026-09-11-001.yaml", _PRE_MARKER_EPOCH)
    payload = _payload("Bash", {"command": "grep -rl keepalive improvement-log/"})

    result = _run(tmp_path, payload)

    assert result.returncode == 2, result.stdout + result.stderr


def test_marker_blocks_grep_tool_path_improvement_log_dir(tmp_path: Path) -> None:
    """2026-09-22-001: Grep 도구의 path 필드가 improvement-log 디렉터리 자체를 가리키면
    막는다 — REP-4 6차 실행에서 이 방식으로 12개 파일을 찾아냈다.
    """
    _touch_marker(tmp_path)
    payload = _payload("Grep", {"pattern": "keepalive", "path": "improvement-log"})

    result = _run(tmp_path, payload)

    assert result.returncode == 2, result.stdout + result.stderr


def test_marker_allows_reading_post_marker_improvement_log_entry(tmp_path: Path) -> None:
    """2026-09-22-001: 마커 뒤에 새로 생긴 후보(실행자가 improvement-log.sh new 로
    발급한 것)는 이 실행에서 실행자 자신이 만든 것이므로 다시 읽을 수 있어야 한다.
    """
    _touch_marker(tmp_path)
    _touch_with_mtime(tmp_path / "improvement-log" / "2026-09-22-010.yaml", _POST_MARKER_EPOCH)
    payload = _payload("Read", {"file_path": "improvement-log/2026-09-22-010.yaml"})

    result = _run(tmp_path, payload)

    assert result.returncode == 0, result.stdout + result.stderr


def test_marker_allows_writing_new_improvement_log_entry(tmp_path: Path) -> None:
    """2026-09-22-001: REP-7 합격 기준이 실행자에게 후보 1건 생성을 요구하므로, 아직
    없는 경로에 쓰는 것은 막지 않는다.
    """
    _touch_marker(tmp_path)
    payload = _payload(
        "Write", {"file_path": "improvement-log/2026-09-22-099.yaml", "content": "x"}
    )

    result = _run(tmp_path, payload)

    assert result.returncode == 0, result.stdout + result.stderr


def test_marker_allows_reading_harness_improvement_log_schema(tmp_path: Path) -> None:
    """2026-09-22-001: harness/improvement-log/ 는 번들의 schema·템플릿·README 라
    실행자가 후보를 쓰려면 읽어야 하므로 막지 않는다.
    """
    _touch_marker(tmp_path)
    payload = _payload("Read", {"file_path": "harness/improvement-log/schema.md"})

    result = _run(tmp_path, payload)

    assert result.returncode == 0, result.stdout + result.stderr


def test_marker_allows_improvement_log_new_command(tmp_path: Path) -> None:
    """2026-09-22-001: improvement-log.sh new 는 REP-7 이 요구하는 후보 생성이라 허용한다."""
    _touch_marker(tmp_path)
    payload = _payload("Bash", {"command": "./harness/scripts/improvement-log.sh new"})

    result = _run(tmp_path, payload)

    assert result.returncode == 0, result.stdout + result.stderr


def test_marker_allows_improvement_log_validate_command(tmp_path: Path) -> None:
    """2026-09-22-001: improvement-log.sh validate 는 자기 후보의 스키마만 확인하므로
    허용한다.
    """
    _touch_marker(tmp_path)
    payload = _payload("Bash", {"command": "./harness/scripts/improvement-log.sh validate"})

    result = _run(tmp_path, payload)

    assert result.returncode == 0, result.stdout + result.stderr


def test_marker_blocks_improvement_log_list_command(tmp_path: Path) -> None:
    """2026-09-22-001: improvement-log.sh list 는 기존 항목의 symptom 요약을 출력해
    task ID 가 새므로 막는다.
    """
    _touch_marker(tmp_path)
    payload = _payload("Bash", {"command": "./harness/scripts/improvement-log.sh list"})

    result = _run(tmp_path, payload)

    assert result.returncode == 2, result.stdout + result.stderr


def test_no_marker_allows_reading_improvement_log_entry(tmp_path: Path) -> None:
    """2026-09-22-001: 마커가 없으면 improvement-log/ 도 평상시처럼 자유롭게 읽는다."""
    _touch_with_mtime(tmp_path / "improvement-log" / "2026-09-20-004.yaml", _PRE_MARKER_EPOCH)
    payload = _payload("Read", {"file_path": "improvement-log/2026-09-20-004.yaml"})

    result = _run(tmp_path, payload)

    assert result.returncode == 0, result.stdout + result.stderr


def test_block_message_states_allowed_scope(tmp_path: Path) -> None:
    """AD-2 2026-09-22-001 후속: REP-7 재실행에서 실행자가 improvement-log/ 전체가
    금지라고 오해해 후보 작성을 포기했다(2026-09-24). 차단 메시지가 새 후보 발급·쓰기는
    계속 허용된다는 것을 명시해야 한다 — `improvement-log.sh new` 호출과 "허용" 문구가
    stderr 에 있어야 한다.
    """
    _touch_marker(tmp_path)
    payload = _payload("Read", {"file_path": "evaluation/tasks/representative.md"})

    result = _run(tmp_path, payload)

    assert result.returncode == 2, result.stdout + result.stderr
    assert "improvement-log.sh new" in result.stderr, result.stderr
    assert "허용" in result.stderr, result.stderr
