"""완료된 단위마다 `docs/step_results/` 에 그 단위의 페이지가 있고, 그 페이지가
다섯 절을 갖는다.

왜 이것을 테스트로 두는가: [../../AGENTS.md](../../AGENTS.md) Learning 은 "전역
지시보다 test, lint, arch-rule, hook, script 를 우선합니다" 라고 정합니다. "단위가
끝나면 결과를 적는다" 를 자연어 지시로 두면 바쁠 때 빠지고, 빠진 것을 아무도
모릅니다. 그래서 검사로 둡니다.

**왜 git 이 아니라 backlog 를 읽는가.** 커밋 trailer(`Unit:`)를 읽는 쪽이 자연스러워
보이지만 CI 의 `verify` job 은 `fetch-depth` 기본값(1)으로 checkout 하므로 거기서는
이력이 없습니다. 이력이 없으면 검사가 조용히 통과하고, 조용히 통과하는 검사는
없는 것과 같습니다. `intents/mvp-backlog.md` 는 단위 상태의 **정본**이고(AGENTS.md)
저장소 안에 있으므로 어디서든 읽힙니다.

**왜 Phase 3 부터인가.** Phase 0~2 는 Phase 당 한 장으로 요약했습니다 — 이유는
`docs/step_results/README.md` 에 있습니다. 과거 26개 단위를 되짚어 쓰는 것은 이
문서의 목적("앞으로 각 단위의 결과가 남는 것")에 기여하지 않습니다.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKLOG = REPO_ROOT / "intents" / "mvp-backlog.md"
STEP_RESULTS = REPO_ROOT / "docs" / "step_results"

FIRST_UNIT_PHASE = 3
"""이 Phase 번호부터 단위별 페이지를 요구합니다."""

REQUIRED_SECTIONS = (
    "## 무엇이 생겼는가",
    "## 왜 그렇게 했는가",
    "## 하네스 근거",
    "## 정한 것과 다른 점",
    "## 남긴 것",
)
"""`docs/step_results/README.md` 의 "한 장이 담아야 하는 것" 표와 같은 다섯 절."""

_ROW = re.compile(r"^\|\s*(P(\d+)-[0-9a-z]+)\s*\|")
_DONE = "완료"


def _completed_units() -> list[str]:
    """backlog 의 단위 표에서 `완료` 로 표시된 Phase 3 이후 단위의 번호."""
    units: list[str] = []
    for line in BACKLOG.read_text(encoding="utf-8").splitlines():
        match = _ROW.match(line)
        if match is None:
            continue
        if _DONE not in line:
            continue
        if int(match.group(2)) < FIRST_UNIT_PHASE:
            continue
        units.append(match.group(1))
    return sorted(set(units))


def _page_for(unit: str) -> Path:
    return STEP_RESULTS / f"{unit.lower()}.md"


def test_backlog_has_completed_units_from_phase_3() -> None:
    """이 테스트의 전제 — backlog 에서 대상 단위를 실제로 찾을 수 있다.

    이 단언이 없으면 정규식이 깨졌을 때 "완료된 단위가 0개" 로 읽혀 아래 두
    테스트가 조용히 통과합니다. 빈 목록에 대한 전칭 명제는 언제나 참입니다.
    """
    assert _completed_units(), (
        f"{BACKLOG.relative_to(REPO_ROOT)} 에서 Phase {FIRST_UNIT_PHASE} 이후의 "
        "완료 단위를 찾지 못했습니다. 표 형식이 바뀌었다면 이 테스트의 정규식을 "
        "함께 고치십시오 — 찾지 못하는 것과 없는 것은 다릅니다."
    )


def test_every_completed_unit_has_a_step_result_page() -> None:
    """완료된 단위마다 페이지가 있다."""
    missing = [unit for unit in _completed_units() if not _page_for(unit).is_file()]
    assert not missing, (
        "완료로 표시된 단위에 step 결과 페이지가 없습니다: "
        f"{missing}. 단위의 PR 에 그 페이지를 함께 넣습니다 — 나중에 몰아 쓰면 "
        "기억이 아니라 추측이 들어갑니다. 형식은 "
        "docs/step_results/README.md 의 '한 장이 담아야 하는 것' 입니다."
    )


def test_every_step_result_page_has_the_required_sections() -> None:
    """단위 페이지는 다섯 절을 갖는다 — 특히 `하네스 근거` 를 비우지 않습니다."""
    offenders: dict[str, list[str]] = {}
    for path in sorted(STEP_RESULTS.glob("*.md")):
        if path.name in {"README.md"} or path.stem.startswith("phase-"):
            continue
        text = path.read_text(encoding="utf-8")
        absent = [section for section in REQUIRED_SECTIONS if section not in text]
        if absent:
            offenders[path.name] = absent

    assert not offenders, (
        "step 결과 페이지에 빠진 절이 있습니다: "
        f"{offenders}. '하네스 근거' 가 비어 있으면 그 단위는 판정되지 않은 "
        "것입니다 — 요구(R-*)·결정(D-*)·단계·증거·후보 다섯 줄을 적습니다."
    )
