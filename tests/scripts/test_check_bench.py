"""AD-2 후보 2026-09-17-004: `scripts/check-bench.sh` 가 smoke bench 결과의 p95 를
`harness.config` 의 `HARNESS_BENCH_P95_MAX_MS` 임계값과 비교해 게이트하는지 검증합니다.

`scripts/smoke.sh --bench` 가 남기는 실제 스키마(`{p50_ms, p95_ms, max_ms, n, warmup,
measured_at, commit, adapter, docker, os}`)의 부분집합만 있으면 충분하므로, 이 테스트는
`p95_ms`·`measured_at` 만 채운 최소 fixture 로 subprocess 실행 결과(종료 코드·마지막
출력 줄)를 검증합니다. 실제 `harness.config`(보호 파일)는 건드리지 않고 임시
`harness.config` 를 만들어 `--config` 로 넘깁니다. 이 테스트는 subprocess 로 bash
스크립트를 실행할 뿐 자체적으로 소켓을 열지 않으므로 `pytest-socket` 의 기본
`--disable-socket` 아래에서도(그리고 `integration` 마크 없이) 돕니다.
"""

from __future__ import annotations

import json
import shutil
import subprocess
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


def _run(bench_path: Path, config_path: Path) -> subprocess.CompletedProcess[str]:
    # bash 로 명시적으로 실행합니다 — Windows 는 shebang 을 직접 해석하지 않습니다.
    return subprocess.run(
        [_BASH, str(SCRIPT_PATH), "--bench", str(bench_path), "--config", str(config_path)],
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
    _write_bench(bench_path, p95_ms=100, measured_at=_now_iso())
    _write_config(config_path, threshold=150)

    result = _run(bench_path, config_path)

    assert result.returncode == 0, result.stdout + result.stderr
    assert _last_line(result.stdout) == "p95=100 ms, 기준=150 ms — 통과"


def test_p95_over_threshold_exits_one(tmp_path: Path) -> None:
    """p95 가 기준을 넘으면 exit 1 이고 마지막 줄에 초과했음이 드러납니다.

    verify.sh 의 summary 는 각 단계 로그의 마지막 줄만 남기므로, 그 한 줄만 보고도
    통과·초과·신선도 실패를 구분할 수 있어야 합니다(리뷰 지적).
    """
    bench_path = tmp_path / "smoke-bench.json"
    config_path = tmp_path / "harness.config"
    _write_bench(bench_path, p95_ms=200, measured_at=_now_iso())
    _write_config(config_path, threshold=150)

    result = _run(bench_path, config_path)

    assert result.returncode == 1, result.stdout + result.stderr
    assert _last_line(result.stdout) == "p95=200 ms, 기준=150 ms — 초과"


def test_stale_measured_at_exits_one(tmp_path: Path) -> None:
    """`measured_at` 이 30분보다 오래되면 기준을 만족해도 exit 1 이고, 마지막 줄에
    "측정이 오래됨" 이 드러나 초과 실패와 구분됩니다(리뷰 지적 — age 는 실행 시점에
    따라 달라지므로 접두사만 고정해 비교합니다).
    """
    bench_path = tmp_path / "smoke-bench.json"
    config_path = tmp_path / "harness.config"
    _write_bench(bench_path, p95_ms=100, measured_at=_iso_minutes_ago(31))
    _write_config(config_path, threshold=150)

    result = _run(bench_path, config_path)

    assert result.returncode == 1, result.stdout + result.stderr
    last_line = _last_line(result.stdout)
    assert last_line.startswith("p95=100 ms, 기준=150 ms — 측정이 오래됨"), last_line
    assert "> 1800s" in last_line, last_line


def test_missing_threshold_variable_exits_one(tmp_path: Path) -> None:
    """`harness.config` 에 `HARNESS_BENCH_P95_MAX_MS` 가 없으면 exit 1 이고 이유를 밝힙니다."""
    bench_path = tmp_path / "smoke-bench.json"
    config_path = tmp_path / "harness.config"
    _write_bench(bench_path, p95_ms=100, measured_at=_now_iso())
    _write_config(config_path, threshold=None)

    result = _run(bench_path, config_path)

    assert result.returncode == 1, result.stdout + result.stderr
    assert "HARNESS_BENCH_P95_MAX_MS" in result.stderr


def test_missing_bench_file_exits_one(tmp_path: Path) -> None:
    """벤치 결과 파일이 없으면 exit 1 이고 이유를 밝힙니다."""
    bench_path = tmp_path / "smoke-bench.json"  # 일부러 만들지 않음
    config_path = tmp_path / "harness.config"
    _write_config(config_path, threshold=150)

    result = _run(bench_path, config_path)

    assert result.returncode == 1, result.stdout + result.stderr
    assert result.stderr.strip() != ""
