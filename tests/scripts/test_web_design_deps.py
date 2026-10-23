"""spec 0007 R-10: `apps/web` 의 시각 라이브러리는 DESIGN.md 1절 표에 먼저 적힙니다.

새 시각 의존이 문서보다 먼저 `package.json` 에 들어오면 이 테스트가 실패합니다. 판정은 둘의
대조입니다 - `dependencies` 의 각 항목이 (a) 1절 표에 백틱으로 적혔거나 (b) 아래 **비시각
목록**에 있어야 합니다. 비시각 목록은 이 테스트 파일에 있으므로 거기에 항목을 더하는 것이
리뷰에 보이는 결정입니다.
"""

from __future__ import annotations

import json
import re

from tests.scripts._fake_docker import REPO_ROOT

DESIGN = REPO_ROOT / "DESIGN.md"
WEB_ROOT = REPO_ROOT / "apps" / "web"
WEB_PACKAGE = WEB_ROOT / "package.json"

# 그리지 않는 의존. 항목마다 왜 비시각인지 적습니다.
NON_VISUAL = {
    "@aether/sdk": "api 호출 클라이언트(워크스페이스 패키지). 화면을 그리지 않는다",
    "next": "프레임워크(DESIGN 1절 첫 행의 Next.js). 라우팅·번들링이다",
    "react": "UI 런타임. 시각 라이브러리가 아니라 모든 화면의 전제",
    "react-dom": "react 의 DOM 렌더러. 위와 같다",
    "cn": "클래스 이름 문자열 결합 유틸. 그리지 않는다",
    "class-variance-authority": "className 변형 헬퍼(DESIGN 3절의 cva). 문자열만 만든다",
}


def design_section_1() -> str:
    text = DESIGN.read_text(encoding="utf-8")
    match = re.search(r"^## 1\. 스택\n(.*?)^## 2\.", text, flags=re.S | re.M)
    assert match, "DESIGN.md 에 '## 1. 스택' 절이 없다"
    return match.group(1)


def documented_packages() -> set[str]:
    """1절 표의 백틱 조각 중 패키지 이름꼴(`@scope/name`, `name`)인 것."""
    return set(re.findall(r"`(@?[a-z0-9][a-z0-9._-]*(?:/[a-z0-9._-]+)?)`", design_section_1()))


def undocumented_dependencies(dependencies: dict[str, str]) -> list[str]:
    documented = documented_packages()
    return sorted(
        name for name in dependencies if name not in documented and name not in NON_VISUAL
    )


def test_every_web_dependency_is_documented_or_declared_non_visual() -> None:
    """R-10: DESIGN.md 1절에 없는 시각 의존이 0건."""
    dependencies = json.loads(WEB_PACKAGE.read_text(encoding="utf-8"))["dependencies"]
    assert undocumented_dependencies(dependencies) == []


def test_a_new_visual_dependency_ahead_of_the_document_is_caught() -> None:
    """R-10: 판정 함수 자체의 검증 - 문서에 없는 의존은 잡힌다."""
    dependencies = {"@xyflow/react": "12.12.0", "some-chart-lib": "1.0.0"}
    assert undocumented_dependencies(dependencies) == ["some-chart-lib"]


def test_the_canvas_dependency_is_in_the_document_and_pinned_exactly() -> None:
    """R-10, H-1: 캔버스 의존은 1절에 있고 package.json 은 캐럿 없이 문서의 그 버전이다."""
    dependencies = json.loads(WEB_PACKAGE.read_text(encoding="utf-8"))["dependencies"]
    assert "@xyflow/react" in documented_packages()
    assert dependencies["@xyflow/react"] == "12.12.0"
    assert "12.12.0" in design_section_1()


def test_only_base_css_of_the_canvas_is_imported() -> None:
    """DESIGN 1절: `dist/base.css` 만 import 하고 기본 테마 `dist/style.css` 는 쓰지 않는다."""
    sources = [
        p
        for ext in ("*.ts", "*.tsx", "*.css")
        for p in WEB_ROOT.rglob(ext)
        if not {"node_modules", ".next"} & set(p.parts) and ".test." not in p.name
    ]
    joined = "\n".join(p.read_text(encoding="utf-8") for p in sources)
    assert "@xyflow/react/dist/base.css" in joined
    assert "@xyflow/react/dist/style.css" not in joined


def canvas_css_block() -> str:
    """`globals.css` 의 캔버스 구간 - 주석 `캔버스(`@xyflow/react`` 부터 파일 끝까지."""
    css = (WEB_ROOT / "app" / "globals.css").read_text(encoding="utf-8")
    start = css.index("@xyflow/react")
    return css[start:]


def test_canvas_css_has_no_hex_literals() -> None:
    """D-1: 캔버스 덮어쓰기에 hex 색 리터럴이 0건 - 색은 토큰(`var(--…)`)뿐이다."""
    assert re.findall(r"#[0-9a-fA-F]{3,8}", canvas_css_block()) == []


def test_attribution_anchor_color_is_overridden_with_a_token() -> None:
    """D-1: base.css 의 `.react-flow__attribution a { color: #999 }` 를 토큰으로 덮는다."""
    block = canvas_css_block()
    match = re.search(r"\.react-flow__attribution\s+a\s*\{([^}]*)\}", block)
    assert match, "anchor 선택자(.react-flow__attribution a)가 없다"
    assert re.search(r"color:\s*var\(--", match.group(1))
