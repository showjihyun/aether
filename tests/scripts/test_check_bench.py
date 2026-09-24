"""AD-2 후보 2026-09-17-004: `scripts/check-bench.sh` 가 smoke bench 결과의 p95 를
`harness.config` 의 `HARNESS_BENCH_P95_MAX_MS` 임계값과 비교해 게이트하는지 검증합니다.

AD-2 후보 2026-09-19-002: 신선도 판정이 벽시계 현재 시각 대신 `.harness/logs/smoke.log`
의 수정 시각(같은 verify 실행에서 나온 측정인지)과 비교하는지 검증합니다 — 같은 실행 안에서
smoke 가 벤치를 기록했는데 프로세스가 느려져 판정이 47분 뒤에 돌아도 측정값이 기준 안이면
통과해야 합니다(2026-09-19 거짓 실패). smoke.log 가 없으면(단독 실행) 기존 벽시계 30분
규칙으로 폴백합니다.

`scripts/smoke.sh --bench` 가 남기는 실제 스키마(`{p50_ms, p95_ms, max_ms, n, warmup,
measured_at, commit, adapter, docker, os}`)의 부분집합만 있으면 충분하므로, 이 테스트는
`p95_ms`·`measured_at` 만 채운 최소 fixture 로 subprocess 실행 결과(종료 코드·마지막
출력 줄)를 검증합니다. 실제 `harness.config`(보호 파일)는 건드리지 않고 임시
`harness.config` 를 만들어 `--config` 로 넘깁니다. smoke.log 도 마찬가지로 임시 파일을
만들어 `--smoke-log` 로 넘겨, 실제 저장소의 `.harness/logs/smoke.log`(하네스 보호 경로)를
읽거나 쓰지 않습니다. 이 테스트는 subprocess 로 bash 스크립트를 실행할 뿐 자체적으로
소켓을 열지 않으므로 `pytest-socket` 의 기본 `--disable-socket` 아래에서도(그리고
`integration` 마크 없이) 돕니다.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "scripts" / "check-bench.sh"

# Windows 의 `CreateProcess` 는 인자 하나짜리 "bash" 를 넘기면 PATH 순서와 무관하게
# System32 의 WSL 런처(App execution alias)를 먼저 찾아 실패합니다(실측, aether-windows
# -pitfalls). `shutil.which` 는 PATH 를 순서대로 직접 훑어 Git Bash 의 절대경로를
# 찾으므로, 그 경로를 argv[0] 로 명시해 이 문제를 피합니다.
_BASH = shutil.which("bash") or "bash"


def _now_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _iso_minutes_ago(minutes: int) -> str:
    return (datetime.now(UTC) - timedelta(minutes=minutes)).strftime("%Y-%m-%dT%H:%M:%SZ")


def _iso_seconds_ago(seconds: int) -> str:
    return (datetime.now(UTC) - timedelta(seconds=seconds)).strftime("%Y-%m-%dT%H:%M:%SZ")


def _write_bench(path: Path, *, p95_ms: float, measured_at: str) -> None:
    path.write_text(
        json.dumps(
            {
                "p50_ms": 50.0,
                "p95_ms": p95_ms,
                "max_ms": p95_ms + 10,
                "n": 180,
                "warmup": 20,
                "measured_at": measured_at,
                "commit": "deadbee",
                "adapter": "fake",
                "docker": "27.3.1",
                "os": "test",
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )


def _write_config(path: Path, *, threshold: int | None) -> None:
    lines = ["# 테스트용 최소 harness.config — 진짜 harness.config 는 건드리지 않습니다."]
    if threshold is not None:
        lines.append(f"HARNESS_BENCH_P95_MAX_MS={threshold}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _touch_smoke_log(path: Path, *, seconds_ago: float) -> None:
    """smoke.log 를 만들고 수정 시각을 `seconds_ago` 만큼 과거로 맞춥니다.

    `os.utime` 으로 mtime 을 직접 지정합니다 — verify 를 실제로 실행하지 않고도
    "같은 실행에서 나온 smoke 로그" 의 수정 시각을 재현할 수 있어야 합니다.
    """
    path.write_text("smoke: pass (test fixture)\n", encoding="utf-8")
    mtime = time.time() - seconds_ago
    os.utime(path, (mtime, mtime))


def _run(
    bench_path: Path,
    config_path: Path,
    *,
    smoke_log_path: Path | None,
) -> subprocess.CompletedProcess[str]:
    # bash 로 명시적으로 실행합니다 — Windows 는 shebang 을 직접 해석하지 않습니다.
    args = [_BASH, str(SCRIPT_PATH), "--bench", str(bench_path), "--config", str(config_path)]
    if smoke_log_path is not None:
        args.extend(["--smoke-log", str(smoke_log_path)])
    return subprocess.run(
        args,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )


def _last_line(output: str) -> str:
    stripped = output.strip()
    return stripped.splitlines()[-1] if stripped else ""


def test_p95_within_threshold_exits_zero(tmp_path: Path) -> None:
    """p95 가 기준 이하면 exit 0 이고 마지막 줄에 실측값과 기준을 함께 출력합니다."""
    bench_path = tmp_path / "smoke-bench.json"
    config_path = tmp_path / "harness.config"
    smoke_log_path = tmp_path / "smoke.log"
    _write_bench(bench_path, p95_ms=100, measured_at=_now_iso())
    _write_config(config_path, threshold=150)
    _touch_smoke_log(smoke_log_path, seconds_ago=0)

    result = _run(bench_path, config_path, smoke_log_path=smoke_log_path)

    assert result.returncode == 0, result.stdout + result.stderr
    assert _last_line(result.stdout) == "p95=100 ms, 기준=150 ms — 통과"


def test_p95_over_threshold_exits_one(tmp_path: Path) -> None:
    """p95 가 기준을 넘으면 exit 1 이고 마지막 줄에 초과했음이 드러납니다.

    verify.sh 의 summary 는 각 단계 로그의 마지막 줄만 남기므로, 그 한 줄만 보고도
    통과·초과·신선도 실패를 구분할 수 있어야 합니다(리뷰 지적).

    AD-2 2026-09-22-002: 초과 시 같은 실행 안에서 재측정이 한 번 더 일어나므로
    (기본 명령은 `scripts/smoke.sh --bench`, 도커가 필요), 이 테스트는 도커 없이
    빠르고 결정적으로 검증하기 위해 `HARNESS_BENCH_REMEASURE_CMD` 로 재측정도
    같은 값(200)을 남기도록 고정합니다 — 2회 연속 초과이므로 최종 결과는 여전히
    exit 1 입니다. 재측정 자체의 세부 동작(1차 초과·2차 이내/초과, 명령 실패,
    미갱신)은 `test_first_over_second_within_exits_zero` 등 전용 테스트가 검증합니다.
    """
    bench_path = tmp_path / "smoke-bench.json"
    config_path = tmp_path / "harness.config"
    smoke_log_path = tmp_path / "smoke.log"
    _write_bench(bench_path, p95_ms=200, measured_at=_now_iso())
    _write_config(config_path, threshold=150)
    _touch_smoke_log(smoke_log_path, seconds_ago=0)

    remeasure_script = tmp_path / "remeasure_same.py"
    remeasure_script.write_text(
        "import json, datetime\n"
        f"path = {str(bench_path)!r}\n"
        "with open(path, 'r', encoding='utf-8') as f:\n"
        "    data = json.load(f)\n"
        "data['p95_ms'] = 200\n"
        "data['measured_at'] = datetime.datetime.now(datetime.UTC).strftime('%Y-%m-%dT%H:%M:%SZ')\n"
        "with open(path, 'w', encoding='utf-8') as f:\n"
        "    json.dump(data, f)\n",
        encoding="utf-8",
    )

    result = _run_with_remeasure(
        bench_path, config_path, smoke_log_path, _remeasure_cmd(remeasure_script)
    )

    assert result.returncode == 1, result.stdout + result.stderr
    last_line = _last_line(result.stdout)
    assert "200" in last_line, last_line
    assert "초과" in last_line, last_line


def test_same_run_slow_execution_exits_zero(tmp_path: Path) -> None:
    """AD-2 2026-09-19-002: smoke 와 bench 가 둘 다 2시간 전이지만 서로 가까우면(60초
    차) 실행 전체가 느렸을 뿐 같은 verify 실행이므로 exit 0 이어야 합니다. 벽시계
    현재 시각과 비교했다면(구 규칙) age=7200s > 1800s 로 거짓 실패했을 사례입니다.
    """
    bench_path = tmp_path / "smoke-bench.json"
    config_path = tmp_path / "harness.config"
    smoke_log_path = tmp_path / "smoke.log"
    _touch_smoke_log(smoke_log_path, seconds_ago=7200)
    _write_bench(bench_path, p95_ms=62.2, measured_at=_iso_seconds_ago(7260))
    _write_config(config_path, threshold=150)

    result = _run(bench_path, config_path, smoke_log_path=smoke_log_path)

    assert result.returncode == 0, result.stdout + result.stderr
    assert _last_line(result.stdout) == "p95=62.2 ms, 기준=150 ms — 통과"


def test_bench_from_previous_run_exits_one(tmp_path: Path) -> None:
    """벤치 결과가 smoke 로그보다 `SAME_RUN_MAX_LAG_SECONDS`(600s) 이상 이전이면
    같은 실행에서 나온 측정이 아니므로 exit 1 이고, 마지막 줄에 사유가 드러납니다.
    2820초 차는 2026-09-19-002 사고에서 실측된 지연(smoke 종료 후 47분 뒤 bench 실행)
    입니다.
    """
    bench_path = tmp_path / "smoke-bench.json"
    config_path = tmp_path / "harness.config"
    smoke_log_path = tmp_path / "smoke.log"
    _touch_smoke_log(smoke_log_path, seconds_ago=0)
    _write_bench(bench_path, p95_ms=62.2, measured_at=_iso_seconds_ago(2820))
    _write_config(config_path, threshold=150)

    result = _run(bench_path, config_path, smoke_log_path=smoke_log_path)

    assert result.returncode == 1, result.stdout + result.stderr
    last_line = _last_line(result.stdout)
    expected = "p95=62.2 ms, 기준=150 ms — 측정이 이전 실행 것(bench 가 smoke 로그보다 2820s 이전)"
    assert last_line == expected, last_line


def test_missing_smoke_log_and_fresh_bench_exits_zero(tmp_path: Path) -> None:
    """`--smoke-log` 경로가 없으면(깨끗한 체크아웃, check-bench.sh 단독 실행) 벽시계
    현재 시각과 비교하는 기존 규칙으로 폴백합니다 — 방금 측정이면 exit 0."""
    bench_path = tmp_path / "smoke-bench.json"
    config_path = tmp_path / "harness.config"
    smoke_log_path = tmp_path / "smoke.log"  # 일부러 만들지 않음
    _write_bench(bench_path, p95_ms=100, measured_at=_now_iso())
    _write_config(config_path, threshold=150)

    result = _run(bench_path, config_path, smoke_log_path=smoke_log_path)

    assert result.returncode == 0, result.stdout + result.stderr
    assert _last_line(result.stdout) == "p95=100 ms, 기준=150 ms — 통과"


def test_missing_smoke_log_and_stale_bench_exits_one(tmp_path: Path) -> None:
    """`--smoke-log` 경로가 없고 측정이 30분보다 오래되면(벽시계 폴백) exit 1 이고
    마지막 줄에 "측정이 오래됨" 이 드러나 초과 실패와 구분됩니다(age 는 실행 시점에
    따라 달라지므로 접두사만 고정해 비교합니다)."""
    bench_path = tmp_path / "smoke-bench.json"
    config_path = tmp_path / "harness.config"
    smoke_log_path = tmp_path / "smoke.log"  # 일부러 만들지 않음
    _write_bench(bench_path, p95_ms=100, measured_at=_iso_minutes_ago(120))
    _write_config(config_path, threshold=150)

    result = _run(bench_path, config_path, smoke_log_path=smoke_log_path)

    assert result.returncode == 1, result.stdout + result.stderr
    last_line = _last_line(result.stdout)
    assert last_line.startswith("p95=100 ms, 기준=150 ms — 측정이 오래됨"), last_line
    assert "> 1800s" in last_line, last_line


def test_missing_threshold_variable_exits_one(tmp_path: Path) -> None:
    """`harness.config` 에 `HARNESS_BENCH_P95_MAX_MS` 가 없으면 exit 1 이고 이유를 밝힙니다."""
    bench_path = tmp_path / "smoke-bench.json"
    config_path = tmp_path / "harness.config"
    smoke_log_path = tmp_path / "smoke.log"
    _write_bench(bench_path, p95_ms=100, measured_at=_now_iso())
    _write_config(config_path, threshold=None)
    _touch_smoke_log(smoke_log_path, seconds_ago=0)

    result = _run(bench_path, config_path, smoke_log_path=smoke_log_path)

    assert result.returncode == 1, result.stdout + result.stderr
    assert "HARNESS_BENCH_P95_MAX_MS" in result.stderr


def test_missing_bench_file_exits_one(tmp_path: Path) -> None:
    """벤치 결과 파일이 없으면 exit 1 이고 이유를 밝힙니다."""
    bench_path = tmp_path / "smoke-bench.json"  # 일부러 만들지 않음
    config_path = tmp_path / "harness.config"
    smoke_log_path = tmp_path / "smoke.log"
    _write_config(config_path, threshold=150)
    _touch_smoke_log(smoke_log_path, seconds_ago=0)

    result = _run(bench_path, config_path, smoke_log_path=smoke_log_path)

    assert result.returncode == 1, result.stdout + result.stderr
    assert result.stderr.strip() != ""


def _run_with_remeasure(
    bench_path: Path,
    config_path: Path,
    smoke_log_path: Path,
    remeasure_cmd: str,
) -> subprocess.CompletedProcess[str]:
    args = [
        _BASH,
        str(SCRIPT_PATH),
        "--bench",
        str(bench_path),
        "--config",
        str(config_path),
        "--smoke-log",
        str(smoke_log_path),
    ]
    env = dict(os.environ)
    env["HARNESS_BENCH_REMEASURE_CMD"] = remeasure_cmd
    return subprocess.run(
        args,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        env=env,
    )


def test_first_over_second_within_exits_zero(tmp_path: Path) -> None:
    """AD-2 2026-09-22-002: 1차 측정이 기준을 넘어도 같은 실행 안에서 재측정한
    2차가 기준 이내면 잡음으로 보고 exit 0 이며, 마지막 줄에 두 측정값이 모두
    드러납니다(2026-09-23 PR #57: 165.6 ms → 재실행 65.9 ms 사례)."""
    bench_path = tmp_path / "smoke-bench.json"
    config_path = tmp_path / "harness.config"
    smoke_log_path = tmp_path / "smoke.log"
    _write_bench(bench_path, p95_ms=165.6, measured_at=_now_iso())
    _write_config(config_path, threshold=150)
    _touch_smoke_log(smoke_log_path, seconds_ago=0)

    remeasure_script = tmp_path / "remeasure.py"
    remeasure_script.write_text(
        "import json\n"
        f"path = {str(bench_path)!r}\n"
        "with open(path, 'r', encoding='utf-8') as f:\n"
        "    data = json.load(f)\n"
        "data['p95_ms'] = 65.9\n"
        "import datetime\n"
        "data['measured_at'] = datetime.datetime.now(datetime.UTC).strftime('%Y-%m-%dT%H:%M:%SZ')\n"
        "with open(path, 'w', encoding='utf-8') as f:\n"
        "    json.dump(data, f)\n",
        encoding="utf-8",
    )
    remeasure_cmd = _remeasure_cmd(remeasure_script)

    result = _run_with_remeasure(bench_path, config_path, smoke_log_path, remeasure_cmd)

    assert result.returncode == 0, result.stdout + result.stderr
    last_line = _last_line(result.stdout)
    assert "165.6" in last_line, last_line
    assert "65.9" in last_line, last_line
    assert "통과" in last_line, last_line


def test_first_over_second_over_exits_one(tmp_path: Path) -> None:
    """1차·2차 측정이 모두 기준을 넘으면 exit 1 이고 마지막 줄에 "2회" 연속 초과가
    드러납니다."""
    bench_path = tmp_path / "smoke-bench.json"
    config_path = tmp_path / "harness.config"
    smoke_log_path = tmp_path / "smoke.log"
    _write_bench(bench_path, p95_ms=165.6, measured_at=_now_iso())
    _write_config(config_path, threshold=150)
    _touch_smoke_log(smoke_log_path, seconds_ago=0)

    remeasure_script = tmp_path / "remeasure.py"
    remeasure_script.write_text(
        "import json\n"
        f"path = {str(bench_path)!r}\n"
        "with open(path, 'r', encoding='utf-8') as f:\n"
        "    data = json.load(f)\n"
        "data['p95_ms'] = 170.2\n"
        "import datetime\n"
        "data['measured_at'] = datetime.datetime.now(datetime.UTC).strftime('%Y-%m-%dT%H:%M:%SZ')\n"
        "with open(path, 'w', encoding='utf-8') as f:\n"
        "    json.dump(data, f)\n",
        encoding="utf-8",
    )
    remeasure_cmd = _remeasure_cmd(remeasure_script)

    result = _run_with_remeasure(bench_path, config_path, smoke_log_path, remeasure_cmd)

    assert result.returncode == 1, result.stdout + result.stderr
    last_line = _last_line(result.stdout)
    assert "165.6" in last_line, last_line
    assert "170.2" in last_line, last_line
    assert "2회" in last_line, last_line


def test_within_threshold_does_not_remeasure(tmp_path: Path) -> None:
    """1차 측정이 기준 이내면 재측정 명령이 실행되지 않습니다 — 재측정 명령이
    마커 파일을 남기게 해 두고 그 파일이 없음을 확인합니다."""
    bench_path = tmp_path / "smoke-bench.json"
    config_path = tmp_path / "harness.config"
    smoke_log_path = tmp_path / "smoke.log"
    marker_path = tmp_path / "remeasure-ran.marker"
    _write_bench(bench_path, p95_ms=100, measured_at=_now_iso())
    _write_config(config_path, threshold=150)
    _touch_smoke_log(smoke_log_path, seconds_ago=0)

    remeasure_cmd = f"touch {marker_path.as_posix()}"

    result = _run_with_remeasure(bench_path, config_path, smoke_log_path, remeasure_cmd)

    assert result.returncode == 0, result.stdout + result.stderr
    assert not marker_path.exists()


def test_remeasure_command_failure_exits_one(tmp_path: Path) -> None:
    """재측정 명령이 0 이 아닌 코드로 끝나면 exit 1 이고 사유가 마지막 줄에
    드러납니다 — 잡음을 이유로 게이트를 열지 않습니다."""
    bench_path = tmp_path / "smoke-bench.json"
    config_path = tmp_path / "harness.config"
    smoke_log_path = tmp_path / "smoke.log"
    _write_bench(bench_path, p95_ms=200, measured_at=_now_iso())
    _write_config(config_path, threshold=150)
    _touch_smoke_log(smoke_log_path, seconds_ago=0)

    remeasure_cmd = "exit 1"

    result = _run_with_remeasure(bench_path, config_path, smoke_log_path, remeasure_cmd)

    assert result.returncode == 1, result.stdout + result.stderr
    last_line = _last_line(result.stdout)
    assert "재측정" in last_line, last_line
    assert "실패" in last_line, last_line


def test_remeasure_stale_result_exits_one(tmp_path: Path) -> None:
    """재측정 명령이 결과 파일을 갱신하지 못하면(같은 오래된 측정) exit 1 이고
    사유가 마지막 줄에 드러납니다."""
    bench_path = tmp_path / "smoke-bench.json"
    config_path = tmp_path / "harness.config"
    smoke_log_path = tmp_path / "smoke.log"
    _write_bench(bench_path, p95_ms=200, measured_at=_now_iso())
    _write_config(config_path, threshold=150)
    _touch_smoke_log(smoke_log_path, seconds_ago=0)

    # 아무 것도 하지 않는 명령 — 결과 파일이 갱신되지 않습니다.
    remeasure_cmd = "true"

    result = _run_with_remeasure(bench_path, config_path, smoke_log_path, remeasure_cmd)

    assert result.returncode == 1, result.stdout + result.stderr
    last_line = _last_line(result.stdout)
    assert "갱신" in last_line, last_line


def _remeasure_cmd(script_path: Path) -> str:
    """가짜 재측정 스크립트를 실행할 셸 명령 문자열을 만듭니다. check-bench.sh 는
    `HARNESS_BENCH_REMEASURE_CMD` 를 `bash -c` 로 실행하므로, 현재 pytest 를 구동
    중인 인터프리터(`sys.executable`)를 그대로 쓰고 경로는 큰따옴표로 감싸 Windows
    의 공백·백슬래시 경로에서도 안전하게 넘깁니다."""
    import sys

    return f'"{sys.executable}" "{script_path}"'
