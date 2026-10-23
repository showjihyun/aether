"""spec 0007 R-4 (P5-6): 위반 사유의 키 집합이 셋에서 같다.

① api 의 `Reason` 열거형(`validation.py`), ② `DESIGN.md` 6절 「Workflow 그래프 위반 사유」 표의
`reason` 칸, ③ 화면의 문장 맵(`apps/web/lib/workflowViolations.ts`). 셋 중 하나에 값이 늘거나
빠지면 실패합니다 - api 에 사유가 늘면 문장 없는 값이 그 자리에서 드러납니다.
"""

from __future__ import annotations

import re

from tests.scripts._fake_docker import REPO_ROOT

VALIDATION = (
    REPO_ROOT / "packages" / "workflow" / "src" / "aether_workflow" / "domain" / "validation.py"
)
DESIGN = REPO_ROOT / "DESIGN.md"
MAP = REPO_ROOT / "apps" / "web" / "lib" / "workflowViolations.ts"


def enum_reasons(text: str) -> set[str]:
    """`class Reason(StrEnum):` 본문의 `NAME = "value"` 값들."""
    match = re.search(r"^class Reason\(StrEnum\):\n((?:[ \t]+.*\n|\n)+)", text, flags=re.M)
    assert match, "validation.py 에 class Reason(StrEnum) 이 없다"
    return set(re.findall(r'^[ \t]+[A-Z_]+\s*=\s*"([a-z_]+)"', match.group(1), flags=re.M))


def design_reasons(text: str) -> set[str]:
    """6절 표 「Workflow 그래프 위반 사유」 의 첫 칸(백틱 안 reason)."""
    start = text.index("**Workflow 그래프 위반 사유**")
    end = text.index("**이 표는 기계가 지킵니다**", start)
    return set(re.findall(r"^\|\s*`([a-z_]+)`\s*\|", text[start:end], flags=re.M))


def map_reasons(text: str) -> set[str]:
    """`VIOLATION_SENTENCE` 객체 리터럴의 키."""
    match = re.search(r"VIOLATION_SENTENCE[^=]*=\s*\{(.*?)\n\};", text, flags=re.S)
    assert match, "workflowViolations.ts 에 VIOLATION_SENTENCE 객체가 없다"
    return set(re.findall(r"^\s*([a-z_]+)\s*:", match.group(1), flags=re.M))


def test_the_three_sources_each_yield_the_documented_fourteen() -> None:
    """공허한 통과를 막는다: 셋 다 열네 개를 읽어야 한다 (docs/api.md 8절)."""
    assert len(enum_reasons(VALIDATION.read_text(encoding="utf-8"))) == 14
    assert len(design_reasons(DESIGN.read_text(encoding="utf-8"))) == 14
    assert len(map_reasons(MAP.read_text(encoding="utf-8"))) == 14


def test_api_enum_design_table_and_sentence_map_have_the_same_keys() -> None:
    """R-4: 셋이 같은 키 집합이다."""
    api = enum_reasons(VALIDATION.read_text(encoding="utf-8"))
    design = design_reasons(DESIGN.read_text(encoding="utf-8"))
    web = map_reasons(MAP.read_text(encoding="utf-8"))
    diff = {
        "api-only": sorted(api - design - web),
        "design-only": sorted(design - api - web),
        "web-only": sorted(web - api - design),
        "not-in-api": sorted((design | web) - api),
        "not-in-design": sorted((api | web) - design),
        "not-in-web": sorted((api | design) - web),
    }
    assert all(not v for v in diff.values()), diff


def test_the_parser_sees_a_value_added_to_the_enum() -> None:
    """판정 함수 자체의 양성 대조: 열거형에 값이 하나 늘면 파서가 그것을 읽는다."""
    text = VALIDATION.read_text(encoding="utf-8").replace(
        'TOOL_NODE_WITHOUT_TARGET = "tool_node_without_target"',
        'TOOL_NODE_WITHOUT_TARGET = "tool_node_without_target"\n    FAKE = "fake_reason"',
    )
    assert enum_reasons(text) - design_reasons(DESIGN.read_text(encoding="utf-8")) == {
        "fake_reason"
    }
