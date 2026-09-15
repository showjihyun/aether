"""spec 0002 2.13, 2.11 (P1-9): `scripts/smoke_client.py` 의 순수 함수 계약.

`percentile` 은 nearest-rank 백분위(보간 없음)이고, `summarize_bench` 는 워밍업 20회를
제외한 뒤 180개 표본으로 p50/p95/max 를 계산합니다. 이 모듈은 `docker compose exec`
안에서 `python - <cmd> < scripts/smoke_client.py` 로 실행되므로, 순수 함수는 컨테이너
없이 여기서 직접 검증합니다(HTTP 왕복 자체는 smoke.sh 의 통합 실행으로만 판정 — 이
테스트 파일은 그 부분을 다루지 않습니다).
"""

from __future__ import annotations

import pytest

from scripts.smoke_client import BENCH_WARMUP, percentile, summarize_bench


def test_percentile_nearest_rank_p50_p95_p100() -> None:
    """spec 0002 2.13: nearest-rank 백분위 — [1..100] 의 p50=50, p95=95, p100=100."""
    values = [float(v) for v in range(1, 101)]
    assert percentile(values, 50) == 50
    assert percentile(values, 95) == 95
    assert percentile(values, 100) == 100


def test_percentile_single_element() -> None:
    """spec 0002 2.13: 원소가 하나면 어느 백분위든 그 값 하나를 돌려줍니다."""
    assert percentile([42.0], 1) == 42.0
    assert percentile([42.0], 50) == 42.0
    assert percentile([42.0], 100) == 42.0


def test_percentile_empty_raises_value_error() -> None:
    """spec 0002 2.13: 빈 입력은 `ValueError` — 조용히 0 이나 None 을 돌려주지 않습니다."""
    with pytest.raises(ValueError):
        percentile([], 50)


def test_summarize_bench_excludes_warmup_and_reports_n_180() -> None:
    """spec 0002 2.13: 200 표본 중 처음 20 회(워밍업)를 제외한 180 회로 요약합니다."""
    # 워밍업 구간은 일부러 큰 값(9999)을 넣어 결과에 새어 들어오면 실패하게 합니다.
    warmup_samples = [9999.0] * BENCH_WARMUP
    measured_samples = [float(v) for v in range(1, 181)]  # 1..180
    durations_ms = warmup_samples + measured_samples

    summary = summarize_bench(durations_ms)

    assert summary["n"] == 180
    assert summary["warmup"] == BENCH_WARMUP
    assert summary["p50_ms"] == 90  # nearest-rank: ceil(0.5*180)=90 -> measured_samples[89]=90
    assert summary["p95_ms"] == 171  # ceil(0.95*180)=171 -> measured_samples[170]=171
    assert summary["max_ms"] == 180


def test_summarize_bench_empty_after_warmup_raises_value_error() -> None:
    """spec 0002 2.13: 워밍업 제외 뒤 표본이 없으면 조용히 넘어가지 않고 예외를 냅니다."""
    with pytest.raises(ValueError):
        summarize_bench([1.0] * BENCH_WARMUP)
