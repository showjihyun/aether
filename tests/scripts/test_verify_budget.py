"""벽시계 예산(`time-budget`)의 값이 **어디에 적혀 있는가**.

사람 결정(showjihyun, 2026-10-17): 예산을 600,000 ms → **900,000 ms** 로 올린다.
근거는 `improvement-log/2026-10-06-002.yaml` 에 있고 요지는 둘이다 — 600초는 단계가
**10개**였던 Phase 0 의 값(spec 0001 D-12)이고 지금은 20개에 컨테이너가 셋이며,
`e2e` 가 더해지면 전량이 약 736,000 ms 가 된다.

이 테스트가 고정하는 것은 **숫자 자체가 아니라 숫자가 사는 자리**다. `verify.sh` 는
`HARNESS_VERIFY_BUDGET_MS` 를 **기본값과 함께** 읽으므로(`${HARNESS_VERIFY_BUDGET_MS:-600000}`),
키 이름을 한 글자만 틀리게 적으면 설정은 **조용히 무시되고** 예산은 600,000 으로 남는다 —
사람이 올린 값이 아무 데도 반영되지 않은 채 "올렸다" 고 믿게 된다. 그래서 둘을 본다.

  1. 저장소의 `harness.config` 가 그 키를 **선언하는가**(결정이 설정에 있는가).
  2. 설정에 적은 값이 **실제로 판정을 바꾸는가**(배선이 살아 있는가).

예산은 사람이 소유하는 값이다(EI-2). 이 테스트는 값을 **옮기지 않고 고정만** 한다.
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

# Windows 의 CreateProcess 는 인자 하나짜리 "bash" 를 System32 의 WSL 런처로 잡습니다
# (test_verify_deferred.py 와 같은 이유로 절대 경로를 씁니다).
_BASH = shutil.which("bash") or "bash"

DECIDED_BUDGET_MS = 900_000
"""사람이 정한 값. 바뀌면 이 테스트가 먼저 빨개진다 — 조용한 상향을 막는 자리다."""

_SANDBOX_CONFIG = """# 테스트용 샌드박스 설정입니다. 단계 명령은 전부 `true` 로 두어
# 이 테스트가 재는 것이 **예산 판정**이지 단계의 내용이 아니게 합니다.
HARNESS_STEPS=(
  "fast-a|correctness|true|true"
)
HARNESS_THRESHOLD=80
HARNESS_VERIFY_BUDGET_MS={budget}
"""


def _config_value(name: str) -> str:
    """저장소의 실제 `harness.config` 를 source 해서 변수 하나를 읽는다 — 파일을 정규식으로
    긁지 않는 이유는 `verify.sh` 도 source 로 읽기 때문이다(같은 경로로 봐야 한다)."""
    script = (
        "set -euo pipefail\n"
        f'source "{(REPO_ROOT / "harness.config").as_posix()}"\n'
        f"printf '%s' \"${{{name}-}}\"\n"
    )
    return subprocess.run(
        [_BASH, "-c", script],
        cwd=REPO_ROOT,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        check=True,
        timeout=60,
    ).stdout.strip()


def test_project_config_declares_the_budget() -> None:
    """예산이 `harness.config` 에 있다 — `verify.sh` 의 기본값에 숨어 있지 않다.

    기본값에만 의지하면 사람이 정한 값이 **보호 파일 밖**(스크립트 기본값)에 있게 되고,
    그 값을 바꾸려면 하네스 스크립트를 고쳐야 한다. 결정은 설정에 적는다.
    """
    declared = _config_value("HARNESS_VERIFY_BUDGET_MS")

    assert declared, (
        "harness.config 에 HARNESS_VERIFY_BUDGET_MS 가 없습니다 — "
        "예산이 verify.sh 의 기본값(600000)에 숨어 있습니다"
    )
    assert declared.isdigit(), f"예산은 ms 정수여야 합니다: {declared!r}"
    assert int(declared) == DECIDED_BUDGET_MS, (
        f"사람이 정한 예산은 {DECIDED_BUDGET_MS} ms 입니다(2026-10-17, "
        f"improvement-log/2026-10-06-002). 설정의 값은 {declared} 입니다 — "
        "숫자를 바꾸려면 그 후보에 근거를 적고 이 테스트를 함께 고치십시오(EI-2)"
    )


@pytest.fixture
def sandbox(tmp_path: Path) -> Path:
    """자기 `harness.config` 를 가진 작은 프로젝트. 번들(`harness/`)은 진짜 파일을 복사한다."""

    def _make(budget_ms: int) -> Path:
        root = tmp_path / f"project-{budget_ms}"
        root.mkdir()
        shutil.copytree(REPO_ROOT / "harness", root / "harness")
        (root / "harness.config").write_text(
            _SANDBOX_CONFIG.format(budget=budget_ms), encoding="utf-8", newline="\n"
        )
        return root

    return _make  # type: ignore[return-value]


def _run_verify(root: Path) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    # 바깥 verify 가 락을 잡은 동안(harness-scripts 단계 안에서) 돌 수 있으므로 테스트
    # 전용 락 경로를 준다(test_verify_lock.py 와 같은 이유).
    env["HARNESS_VERIFY_LOCK_DIR"] = str(root / ".harness" / "test.lock")
    env.pop("HARNESS_VERIFY_BUDGET_MS", None)  # 환경이 설정을 가리지 않게 한다
    return subprocess.run(
        [_BASH, str(root / "harness" / "scripts" / "verify.sh"), "--full"],
        cwd=root,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        timeout=600,
    )


def _verify_json(root: Path) -> dict[str, Any]:
    data = json.loads((root / ".harness" / "verify.json").read_text(encoding="utf-8"))
    assert isinstance(data, dict), data
    return data


def test_config_budget_is_what_verify_compares_against(sandbox: Any) -> None:
    """설정에 적은 값이 판정을 바꾼다 — 키 이름이 틀리면 이 테스트가 잡는다.

    예산 1 ms 면 어떤 실행도 넘기므로 `time-budget` 이 **선택 실패**로 집계되고, 그래도
    종료 코드는 0 이다(선택 실패는 게이트를 막지 않는다). 예산이 넉넉하면 그 항목이 없다.
    같은 샌드박스·같은 단계로 둘을 비교하므로 차이를 만든 것은 설정값뿐이다.
    """
    tight = sandbox(1)
    result = _run_verify(tight)
    assert result.returncode == 0, result.stdout + result.stderr
    data = _verify_json(tight)
    assert data["budget_exceeded"] is True, (
        "예산 1 ms 인데 초과로 집계되지 않았습니다 — 설정의 "
        f"HARNESS_VERIFY_BUDGET_MS 가 verify.sh 에 닿지 않습니다: {data}"
    )
    assert data["failed_optional"] >= 1, data.get("failed_optional")
    assert data["budget_ms"] == 1, data.get("budget_ms")

    loose = sandbox(900_000)
    result = _run_verify(loose)
    assert result.returncode == 0, result.stdout + result.stderr
    data = _verify_json(loose)
    assert data["budget_exceeded"] is False, data
    assert data["failed_optional"] == 0, data.get("failed_optional")
    assert data["budget_ms"] == 900_000, data.get("budget_ms")
