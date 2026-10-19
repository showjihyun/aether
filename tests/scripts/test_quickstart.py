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
