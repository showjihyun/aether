"""spec 0006 R-8, R-9, C-5, D-12 (MVP-3): `scripts/e2e.sh` - 가짜 docker 로 **순서·이름 검사·
실패 판정**만 본다. 실제 compose 시나리오(진짜 소형 모델)는 스크립트를 단독 실행해 본다."""

from __future__ import annotations

from pathlib import Path

from tests.scripts._fake_docker import run_script

PROJECT = "aether-e2e-t"
MODEL = "qwen2.5:0.5b"
SERVED = '[GIN] | 200 | POST "/v1/chat/completions"'
GOOD_LOGS = (
    f"aether-worker: 모델 '{MODEL}' 이 볼륨에 없습니다. scripts/fetch-model.sh {MODEL} | {SERVED}"
)
# 1차(빈 볼륨)는 worker 가 죽어 up 이 실패하고, 2차(오프라인)는 성공한다.
HAPPY = {
    "E2E_PROJECT": PROJECT,
    "FAKE_UP_EXIT_SEQ": "1 0",
    "FAKE_LOGS": GOOD_LOGS,
    "E2E_NO_BUILD": "1",
    "FAKE_PS_Q": "llm-running",
}


def _run(tmp_path: Path, env: dict[str, str] | None = None):  # type: ignore[no-untyped-def]
    return run_script(tmp_path, "e2e.sh", [], {**HAPPY, **(env or {})})


def _ups(calls: list[str]) -> list[int]:
    return [i for i, c in enumerate(calls) if " up " in f" {c} "]


def test_rejects_dangerous_project_names_before_any_docker_call(tmp_path: Path) -> None:
    """improvement-log 2026-09-22-003: 이름이 비면 `down -v` 가 개발 볼륨을 지운다 - 거부."""
    for i, bad in enumerate(("", "docker", "aether-dev", "Bad Name", "x")):
        result, calls = run_script(tmp_path / f"n{i}", "e2e.sh", [], {"E2E_PROJECT": bad})
        assert result.returncode == 2, (bad, result.stderr)
        assert calls == [], (bad, calls)


def test_every_down_carries_the_isolated_project_name(tmp_path: Path) -> None:
    """improvement-log 2026-09-22-003: 어떤 경로로 끝나든 `down` 은 `-p <e2e 프로젝트>` 와 함께."""
    result, calls = _run(tmp_path, {"FAKE_ALL_EXIT": "1"})

    assert result.returncode != 0
    downs = [c for c in calls if " down" in f" {c}"]
    assert downs, calls
    assert all(f"-p {PROJECT} " in f"{c} " for c in downs), downs


def test_happy_path_order_empty_volume_then_fetch_then_offline(tmp_path: Path) -> None:
    """R-8/R-9: (1) 빈 볼륨 up 이 멈춘다 (2) 그 뒤에 소형 모델을 받는다 (3) 오프라인 up 이 성공."""
    result, calls = _run(tmp_path)

    assert result.returncode == 0, result.stdout + result.stderr
    ups = _ups(calls)
    assert len(ups) == 2, calls
    pull = next(i for i, c in enumerate(calls) if f"ollama pull {MODEL}" in c)
    assert ups[0] < pull < ups[1], calls
    assert "compose.offline.yaml" not in calls[ups[0]]
    assert "compose.offline.yaml" in calls[ups[1]]
    assert "compose.llm.yaml" in calls[ups[0]] and "compose.llm.yaml" in calls[ups[1]]
    assert all(f"-p {PROJECT} " in f"{c} " for c in calls if c.startswith("compose")), calls


def test_down_between_phases_keeps_the_model_volume(tmp_path: Path) -> None:
    """R-8: 네트워크를 갈아 끼우려고 내리지만 모델 볼륨은 지우지 않는다(`-v` 는 맨 끝)."""
    _, calls = _run(tmp_path)

    ups = _ups(calls)
    between = [c for c in calls[ups[0] : ups[1]] if " down" in f" {c}"]
    assert between, calls
    assert not any(" -v" in c or "--volumes" in c for c in between), between


def test_empty_volume_that_boots_anyway_fails_r9(tmp_path: Path) -> None:
    """R-9: 모델이 없는데 worker 가 떠 버리면(= 조용히 통과) e2e 가 실패해야 한다."""
    result, _ = _run(tmp_path, {"FAKE_UP_EXIT_SEQ": "0 0"})

    assert result.returncode != 0
    assert "R-9" in result.stderr


def test_empty_volume_failure_without_the_fetch_hint_fails_r9(tmp_path: Path) -> None:
    """R-9: 멈추긴 했지만 메시지에 받는 방법이 없으면 '명확한 오류' 가 아니다."""
    result, _ = _run(tmp_path, {"FAKE_LOGS": "Traceback: model not found"})

    assert result.returncode != 0
    assert "fetch-model.sh" in result.stderr


def test_non_succeeded_run_fails_r8(tmp_path: Path) -> None:
    """R-8: Run 이 succeeded 가 아니면 실패."""
    result, _ = _run(tmp_path, {"FAKE_SCENARIO_JSON": '{"run_id":"r","status":"failed"}'})

    assert result.returncode != 0
    assert "R-8" in result.stderr


def test_reachable_outside_world_means_not_offline(tmp_path: Path) -> None:
    """C-5: 외부 접속이 되면 '끊었다' 를 증명하지 못한 것 - succeeded 여도 실패."""
    result, _ = _run(tmp_path, {"FAKE_PROBE_EXIT": "7"})

    assert result.returncode != 0
    assert "C-5" in result.stderr


def test_succeeded_without_a_request_reaching_the_model_server_fails_r8(tmp_path: Path) -> None:
    """R-8: succeeded 여도 llm 서버가 chat 요청을 받은 흔적이 없으면(= fake 가 답했을 수 있다)
    '진짜 openai-호환 서버로' 라는 단언이 비는 것 - 실패."""
    result, _ = _run(tmp_path, {"FAKE_LOGS": GOOD_LOGS.replace(SERVED, "")})

    assert result.returncode != 0
    assert "R-8" in result.stderr
    assert "chat/completions" in result.stderr
