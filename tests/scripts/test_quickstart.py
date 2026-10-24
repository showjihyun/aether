"""spec 0006 R-12, D-21 (MVP-5): `docs/quickstart.md` 가 **실재하는 것만** 가리키는가.

TTFSA 는 이 문서 하나로 측정됩니다 — 문서가 없는 파일·환경변수·명령을 가리키면 측정이
그 자리에서 막히고, 재는 것이 "저장소의 마찰" 이 아니라 "문서의 거짓" 이 됩니다. 이
저장소는 **문서가 API 에 없는 값을 요구한 일이 세 번** 있었고(`improvement-log/
2026-10-18-005`), 그 후보가 제안한 doc 쪽 검사의 **작은 판**이 이 파일입니다.

고정하지 **못하는** 것: 명령이 실제로 동작하는가(그것은 사람의 측정과 `smoke`·`e2e` 의
몫입니다). 여기서 보는 것은 **가리키는 대상이 있는가** 뿐입니다.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
QUICKSTART = REPO_ROOT / "docs" / "quickstart.md"
ENV_EXAMPLE = REPO_ROOT / "infra" / "docker" / ".env.example"
FETCH_MODEL = REPO_ROOT / "scripts" / "fetch-model.sh"
CLI_DOC = REPO_ROOT / "docs" / "cli.md"

# 문서 안의 저장소 상대 경로(코드 블록과 본문 모두). 링크 문법은 `links` 단계가 봅니다.
_PATHS = re.compile(r"(?<![\w./-])((?:apps|packages|infra|scripts|harness|docs)/[\w./-]+)")
_ENV_KEYS = re.compile(r"\bAETHER_[A-Z0-9_]+\b")
_AETHER_SUBCOMMANDS = re.compile(r"\baether (agent|run|runs|up)\b")


def _text() -> str:
    return QUICKSTART.read_text(encoding="utf-8")


def test_quickstart_exists() -> None:
    """R-12: 측정 대상 문서가 없으면 측정할 것이 없습니다."""
    assert QUICKSTART.is_file(), f"{QUICKSTART} 가 없습니다"


def _git_ignores(path: str) -> bool:
    """`.gitignore` 가 가리는 경로인가. 측정자가 **직접 만드는** 파일(`infra/docker/.env`)은
    깨끗한 체크아웃에 없는 것이 정상이고, 있으면 오히려 비밀값이 커밋된 것입니다.

    로컬에만 있는 파일을 실재로 보면 이 테스트가 **로컬에서만 초록**이 됩니다 - 2026-10-19
    에 CI 가 그것을 잡았습니다(`improvement-log/2026-10-19-001`). 그래서 "있다" 가 아니라
    "있거나, git 이 가린다" 를 봅니다.
    """
    result = subprocess.run(
        ["git", "check-ignore", "-q", "--", path],
        cwd=REPO_ROOT,
        capture_output=True,
        check=False,
    )
    return result.returncode == 0


def test_every_repo_path_it_mentions_exists() -> None:
    """문서가 없는 파일을 가리키면 그 줄에서 측정이 막힙니다."""
    missing = sorted(
        {
            candidate
            for candidate in (c.rstrip(".,)") for c in _PATHS.findall(_text()))
            if not (REPO_ROOT / candidate).exists() and not _git_ignores(candidate)
        }
    )
    assert not missing, f"quickstart 가 없는 경로를 가리킵니다: {missing}"


def test_the_env_file_it_tells_you_to_create_is_gitignored() -> None:
    """위 테스트가 `.env` 를 통과시키는 **이유**를 고정합니다. 그 파일이 어느 날 추적
    대상이 되면(= 비밀값이 커밋될 수 있는 상태) 여기서 드러나야 합니다."""
    assert _git_ignores("infra/docker/.env"), ".env 가 더 이상 gitignore 되지 않습니다"
    assert (REPO_ROOT / "infra" / "docker" / ".env.example").is_file()


def test_every_env_key_it_mentions_is_in_env_example() -> None:
    """`.env` 를 채우라고 하면서 없는 키를 적으면 그 줄은 거짓입니다."""
    known = set(_ENV_KEYS.findall(ENV_EXAMPLE.read_text(encoding="utf-8")))
    # CLI 가 읽는 두 변수는 compose 의 `.env` 가 아니라 셸 환경입니다(docs/cli.md).
    known |= {"AETHER_API_KEY", "AETHER_API_URL", "AETHER_VERSION"}
    # 문서가 가리키는 스크립트가 **직접 읽는** 변수도 실재입니다(예: `AETHER_FETCH_PROJECT`).
    # 예외 목록에 이름을 적는 대신 그 스크립트에서 찾습니다 - 스크립트가 그 손잡이를 없애면
    # 이 테스트가 그 자리에서 실패해야 합니다.
    known |= set(_ENV_KEYS.findall(FETCH_MODEL.read_text(encoding="utf-8")))
    unknown = sorted(set(_ENV_KEYS.findall(_text())) - known)
    assert not unknown, f"quickstart 가 모르는 환경변수를 적습니다: {unknown}"


def test_the_small_model_tag_matches_fetch_model_script() -> None:
    """D-21: 판정·Quickstart 가 쓰는 소형 모델 태그는 `fetch-model.sh` 의 것과 같아야
    합니다 - 다르면 받은 모델과 찾는 모델이 어긋나 worker 가 멈춥니다."""
    script = FETCH_MODEL.read_text(encoding="utf-8")
    tag = re.search(r'^TEST_MODEL="([^"]+)"', script, re.MULTILINE)
    assert tag, "fetch-model.sh 에서 TEST_MODEL 을 찾지 못했습니다"
    assert tag.group(1) in _text(), f"quickstart 가 소형 모델 태그 {tag.group(1)} 를 적지 않습니다"


def test_every_aether_subcommand_it_uses_is_documented() -> None:
    """없는 하위 명령을 적으면 측정자가 `exit 2` 를 만납니다."""
    documented = set(_AETHER_SUBCOMMANDS.findall(CLI_DOC.read_text(encoding="utf-8")))
    used = set(_AETHER_SUBCOMMANDS.findall(_text()))
    assert used, "quickstart 가 `aether` 명령을 하나도 쓰지 않습니다 - CLI 가 제품의 입구입니다"
    unknown = sorted(used - documented)
    assert not unknown, f"quickstart 가 docs/cli.md 에 없는 명령을 씁니다: {unknown}"


def test_it_says_what_the_measured_number_does_not_cover() -> None:
    """D-21 의 절반: 소형 모델로 쟀다는 사실과 제품 모델이 따로라는 것을 문서가 말해야
    합니다. 적지 않으면 그 숫자가 "제품을 쓸 수 있는 상태까지" 로 읽힙니다."""
    text = _text()
    assert "qwen3.8:27b" in text, "제품 기본 모델이 따로라는 절이 없습니다"
    assert "D-21" in text, "어느 결정으로 이 경로를 골랐는지 적혀 있지 않습니다"


def test_measurement_template_asks_for_the_five_fields() -> None:
    """spec 2.7: 측정자·환경·단계별 시각·막힌 지점·총 시간. 양식이 묻지 않으면 기록이
    비고, 비어 있는 기록은 R-12 를 만족시키지 못합니다."""
    template = REPO_ROOT / "docs" / "measurements" / "ttfsa-TEMPLATE.md"
    assert template.is_file(), f"{template} 가 없습니다"
    text = template.read_text(encoding="utf-8")
    for field in ("측정자", "환경", "막힌 지점", "총 시간"):
        assert field in text, f"양식에 '{field}' 가 없습니다"


# 아래 둘은 2026-10-20 의 dry-run 이 찾은 마찰을 고정합니다
# (docs/measurements/ttfsa-agent-dryrun-2026-10-20.md 의 F-2·F-4).
# 고친 자리가 다음 편집에서 조용히 사라지는 것을 막습니다.

_PREREQ_TABLE = re.compile(r"## 0\. 필요한 것(.*?)\n## ", re.S)
# 본문이 "실행하라" 고 주는 명령의 첫 낱말. 이 표에 없으면 측정자가 없는 도구를 만납니다.
_TOOLS_THE_DOC_RUNS = ("docker", "git", "uv", "openssl", "curl")


def test_the_prereq_table_lists_every_tool_the_doc_tells_you_to_run() -> None:
    """F-4: 2절이 `openssl` 을 쓰는데 0절 표에는 Docker·git·uv 셋뿐이었습니다.
    없는 도구를 만나는 자리가 측정의 첫 막힘이 됩니다."""
    text = _text()
    table = _PREREQ_TABLE.search(text)
    assert table, "0절 '필요한 것' 표를 찾지 못했습니다"
    listed = table.group(1)
    missing = [
        tool
        for tool in _TOOLS_THE_DOC_RUNS
        if re.search(rf"(?<![\w-]){tool}(?![\w-])", text) and tool not in listed
    ]
    assert not missing, f"문서가 쓰는 도구가 0절 표에 없습니다: {missing}"


def test_quickstart_tells_you_how_to_see_that_the_stack_actually_came_up() -> None:
    """F-2: 4절의 유일한 확인이 `curl /healthz` 였고, 그것은 **worker 가 죽어도 ok** 입니다
    (`/healthz` 는 설계상 DB·worker 를 보지 않습니다 - P0-2). 실제로 깨진 것을 알려 주는
    것은 compose 의 종료 코드와 서비스 상태이므로, 문서가 그 둘을 적어야 합니다."""
    text = _text()
    assert "docker compose" in text and "ps" in text, "서비스 상태를 보는 방법이 없습니다"
    assert re.search(r"docker compose[^\n]*\bps\b", text), (
        "`docker compose ... ps` 가 없습니다 - healthz 는 worker 의 죽음을 보지 않습니다"
    )
    assert "logs" in text, "worker 로그를 보라는 안내가 없습니다"


# 아래 셋은 2026-10-24 의 실측이 찾은 마찰을 고정합니다 (F-10·F-11·F-12).

_FENCE = re.compile(r"```(\w*)\n(.*?)```", re.S)
_COMPOSE_YAML = REPO_ROOT / "infra" / "docker" / "compose.yaml"


def _section(title: str) -> str:
    match = re.search(rf"^## {re.escape(title)}\n(.*?)(?=^## |\Z)", _text(), re.S | re.M)
    assert match, f"'{title}' 절을 찾지 못했습니다"
    return match.group(1)


def test_cleanup_command_names_both_compose_files() -> None:
    """F-10: 정리 명령이 `compose.yaml` 하나만 이름 부르면 `llm` 서비스가 **보이지 않아**
    `down -v` 가 그 컨테이너와 모델 볼륨(397 MB)을 지우지 못하고, 네트워크도 `Resource is
    still in use` 로 남습니다. 그런데 문서는 "-v 가 모델까지 지웁니다" 라고 적고 있었습니다.
    """
    down = [line for line in _section("다 끝내고 지우기").splitlines() if " down" in line]
    assert down, "정리 절에 `down` 명령이 없습니다"
    command = " ".join(down)
    assert "infra/docker/compose.yaml" in command
    assert "infra/docker/compose.llm.yaml" in command, (
        "정리 명령이 compose.llm.yaml 을 빼면 llm 서비스(모델 볼륨의 주인)가 보이지 않습니다"
    )


def test_llm_service_is_hidden_behind_a_profile_in_the_base_compose_file() -> None:
    """F-10 의 **이유**: 기본 파일의 `llm:` 블록은 `profiles:` 뒤에 있고 그것을 벗기는 것은
    오버레이(compose.llm.yaml)입니다. 이 단언이 깨지면(프로파일이 사라지면) 위 테스트가
    요구하는 두 파일이 불필요해졌다는 뜻이니 문서의 한 줄 설명도 함께 고치십시오."""
    block = re.search(r"^  llm:\n((?:    .*\n|\n)*)", _COMPOSE_YAML.read_text("utf-8"), re.M)
    assert block, "compose.yaml 에서 llm 서비스를 찾지 못했습니다"
    assert "profiles:" in block.group(1)
    overlay = (REPO_ROOT / "infra" / "docker" / "compose.llm.yaml").read_text("utf-8")
    assert "profiles: !reset []" in overlay


def test_ps_that_the_doc_says_shows_exited_services_has_dash_a() -> None:
    """F-11: 4절 주석이 "`migrate` 가 `Exited (0)` 인 것은 정상" 이라고 했지만 `ps` 는 `-a`
    없이는 종료된 컨테이너를 **출력하지 않습니다.** 읽는 사람은 있을 수 없는 줄을 찾다가
    "migrate 가 안 돌았다" 로 결론 냅니다 - 정확히 반대의 경보입니다."""
    text = _text()
    assert "Exited" in text, "Exited 를 설명하는 주석이 사라졌습니다 - 이 테스트를 재검토하십시오"
    ps_lines = [ln for ln in text.splitlines() if re.search(r"docker compose[^\n]*\bps\b", ln)]
    assert ps_lines
    missing = [ln for ln in ps_lines if not re.search(r"\bps\b[^\n#]*\s-a\b", ln)]
    assert not missing, f"`ps` 에 -a 가 없습니다: {missing}"


def test_exit_code_is_read_in_the_same_block_as_the_up_command() -> None:
    """F-12: `$?` 는 **직전** 명령의 종료 코드입니다. `up` 과 `echo $?` 사이에 산문과 다른
    블록이 끼어 있으면 `ps` 를 먼저 돌린 사람이 다른 명령의 상태를 읽습니다. 종료 코드를
    `up` 명령과 같은 블록에서 같은 줄로 내야 합니다."""
    blocks = {lang: body for lang, body in _FENCE.findall(_text()) if "up --build" in body}
    # PowerShell 의 `$?` 는 불리언이라 등가물은 `$LASTEXITCODE` 입니다. 한쪽 셸에만 확인을
    # 주면 다른 셸 사용자에게는 F-2 의 1번 확인이 없습니다.
    expected = {"bash": r"\$\?", "powershell": r"\$LASTEXITCODE"}
    assert set(blocks) == set(expected), (
        f"`up` 블록이 bash·powershell 둘이어야 합니다: {set(blocks)}"
    )
    for lang, exit_var in expected.items():
        assert re.search(
            rf'up --build[^\n]*;\s*echo "exit={exit_var}"',
            blocks[lang].replace("\\\n", " "),
        ), f'{lang} `up` 명령 끝에 `; echo "exit=…"` 가 없습니다'
    assert "echo $?" not in _text(), "직전 명령이 불확실한 `echo $?` 가 남아 있습니다"
