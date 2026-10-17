"""spec 0006 D-5, D-12, R-9 (MVP-3): `scripts/fetch-model.sh` - 사람이 네트워크 있는 환경에서
1회 실행해 모델을 볼륨에 적재한다. 가짜 docker 로 인자 조립·멱등·실패 종료만 본다."""

from __future__ import annotations

from pathlib import Path

from tests.scripts._fake_docker import REPO_ROOT, run_script

LISTED = "NAME ID SIZE MODIFIED\nqwen2.5:0.5b abc 397 MB 1 minute ago"


def _pulls(calls: list[str]) -> list[str]:
    return [c for c in calls if " ollama pull " in f" {c} "]


def test_default_model_is_the_product_default(tmp_path: Path) -> None:
    """spec D-12: 인자가 없으면 제품 기본값 `qwen3.8:27b` 를 받는다."""
    result, calls = run_script(tmp_path, "fetch-model.sh", [])

    assert result.returncode == 0, result.stderr
    pulls = _pulls(calls)
    assert len(pulls) == 1 and pulls[0].endswith("ollama pull qwen3.8:27b"), calls


def test_test_model_flag_pulls_the_small_judging_model(tmp_path: Path) -> None:
    """spec D-12: `--test-model` 은 판정 전용 소형 모델 `qwen2.5:0.5b`."""
    result, calls = run_script(tmp_path, "fetch-model.sh", ["--test-model"])

    assert result.returncode == 0, result.stderr
    assert _pulls(calls)[0].endswith("ollama pull qwen2.5:0.5b"), calls


def test_explicit_model_wins_over_test_model_and_env(tmp_path: Path) -> None:
    """D-5: `--model` 이 `--test-model` 과 환경변수보다 앞선다."""
    result, calls = run_script(
        tmp_path,
        "fetch-model.sh",
        ["--test-model", "--model", "tiny:1b"],
        {"AETHER_FETCH_MODEL": "env:2b"},
    )

    assert result.returncode == 0, result.stderr
    assert _pulls(calls)[0].endswith("ollama pull tiny:1b"), calls


def test_env_variable_sets_the_model(tmp_path: Path) -> None:
    """D-5: 인자가 없으면 `AETHER_FETCH_MODEL` 이 기본값을 대신한다."""
    result, calls = run_script(tmp_path, "fetch-model.sh", [], {"AETHER_FETCH_MODEL": "env:2b"})

    assert result.returncode == 0, result.stderr
    assert _pulls(calls)[0].endswith("ollama pull env:2b"), calls


def test_idempotent_when_the_model_is_already_present(tmp_path: Path) -> None:
    """MVP-3 멱등: 이미 있으면 다시 받지 않고 그 사실을 출력한다."""
    result, calls = run_script(
        tmp_path, "fetch-model.sh", ["--test-model"], {"FAKE_OLLAMA_LIST": LISTED}
    )

    assert result.returncode == 0, result.stderr
    assert _pulls(calls) == [], calls
    assert "already" in result.stdout.lower()


def test_pull_failure_exits_nonzero_and_says_what_to_do(tmp_path: Path) -> None:
    """R-9: 네트워크가 없어 pull 이 실패하면 실패 종료 - 조용한 성공이 아니다."""
    result, _ = run_script(tmp_path, "fetch-model.sh", ["--test-model"], {"FAKE_PULL_EXIT": "1"})

    assert result.returncode != 0
    assert "network" in result.stderr.lower()
    assert "qwen2.5:0.5b" in result.stderr


def test_up_failure_exits_nonzero(tmp_path: Path) -> None:
    """R-9: llm 서비스를 못 띄우면(이미지 pull 실패 등) 실패 종료."""
    result, calls = run_script(tmp_path, "fetch-model.sh", [], {"FAKE_UP_EXIT": "1"})

    assert result.returncode != 0
    assert _pulls(calls) == []
    assert result.stderr.strip() != ""


def test_pull_that_leaves_no_model_is_not_success(tmp_path: Path) -> None:
    """R-9: pull 이 0 으로 끝나도 목록에 없으면 성공이 아니다(적재를 눈으로 확인한다)."""
    # pull 은 0 으로 끝나는데 목록에는 안 나타나는 서버: 기록하지 않는 pull 을 흉내낸다.
    result, _ = run_script(
        tmp_path, "fetch-model.sh", ["--test-model"], {"FAKE_PULL_EXIT": "0", "FAKE_NO_RECORD": "1"}
    )

    assert result.returncode != 0
    assert "not" in result.stderr.lower()


def test_never_deletes_anything(tmp_path: Path) -> None:
    """AGENTS.md: 적재 스크립트는 `down`·볼륨 삭제를 하지 않는다."""
    _, calls = run_script(tmp_path, "fetch-model.sh", ["--test-model"])

    joined = "\n".join(calls)
    assert " down" not in joined
    assert "volume rm" not in joined


def test_rejects_empty_project_before_any_docker_call(tmp_path: Path) -> None:
    """improvement-log 2026-09-22-003: 비어 있거나 기본 이름인 프로젝트는 docker 전에 거부."""
    for bad in ("", "docker", "Bad Name"):
        result, calls = run_script(tmp_path / f"p{len(bad)}", "fetch-model.sh", ["--project", bad])
        assert result.returncode == 2, (bad, result.stderr)
        assert calls == [], (bad, calls)


def test_stops_llm_only_when_this_script_started_it(tmp_path: Path) -> None:
    """꺼져 있던 llm 은 끝나고 멈추고(RAM), 이미 떠 있던 것은 건드리지 않는다."""
    _, started = run_script(tmp_path / "a", "fetch-model.sh", ["--test-model"], {"FAKE_PS_Q": ""})
    _, running = run_script(
        tmp_path / "b", "fetch-model.sh", ["--test-model"], {"FAKE_PS_Q": "abc123"}
    )

    assert any(" stop llm" in f" {c}" for c in started), started
    assert not any(" stop llm" in f" {c}" for c in running), running


def test_temp_env_file_is_removed(tmp_path: Path) -> None:
    """AGENTS.md Trust: 임시 `.env`(랜덤 비밀값)는 끝나면 남지 않는다."""
    before = set(REPO_ROOT.glob(".env.fetch.*"))

    run_script(tmp_path, "fetch-model.sh", ["--test-model"])

    assert set(REPO_ROOT.glob(".env.fetch.*")) == before


def test_readme_starts_the_llm_stack_in_the_project_that_holds_the_model() -> None:
    """적재와 기동이 **같은 compose 프로젝트**여야 한다 - 다르면 볼륨이 다르고, 받아 둔
    모델이 스택에 보이지 않는다.

    compose 는 `-p` 가 없으면 프로젝트 이름을 compose 파일의 디렉터리(`docker`)에서
    가져오므로, README 의 명령에 `-p` 가 없으면 볼륨이 `docker_ollama_models` 가 되고
    `fetch-model.sh` 가 적재한 `aether-dev_ollama_models` 와 **다른 볼륨**이 된다. 그러면
    worker 가 "볼륨에 없다" 로 멈추고, 사람은 받아 둔 모델을 눈으로 보면서 그 오류를 읽는다
    (2026-10-18 리뷰에서 실제로 발견된 이음새다).
    """
    default_project = ""
    for line in (REPO_ROOT / "scripts" / "fetch-model.sh").read_text(encoding="utf-8").splitlines():
        if line.startswith("PROJECT=") and "AETHER_FETCH_PROJECT" in line:
            default_project = line.split("-", 1)[1].rstrip('}"')
            break
    assert default_project, "fetch-model.sh 의 기본 프로젝트를 읽지 못했습니다"

    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    commands = [
        line
        for line in readme.splitlines()
        if "compose.llm.yaml" in line and line.lstrip().startswith("docker compose")
    ]
    assert commands, "README 에 compose.llm.yaml 을 얹는 명령이 없습니다"
    for command in commands:
        assert f"-p {default_project}" in command, (
            f"README 의 명령이 적재 프로젝트({default_project})와 다른 프로젝트로 띄웁니다 "
            f"- 모델 볼륨이 갈라집니다: {command}"
        )
