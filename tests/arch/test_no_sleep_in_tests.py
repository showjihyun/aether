"""spec 0002 R-11, D-14: 테스트는 `sleep` 으로 기다리지 않습니다 — 시간은 주입하거나
`tests/support/waiting.py` 의 `wait_until` 로 폴링합니다.

grep 기반 검사는 두 방향으로 틀립니다 — docstring/주석에 적힌 `"time.sleep(...)"` 라는
글자를 오탐하고, `from time import sleep as _s` 처럼 별칭이 붙은 호출은 놓칩니다.
이 테스트는 **`ast`** 로 각 파일을 파싱해 실제 `Call` 노드만 봅니다: `time.sleep(...)`,
`asyncio.sleep(...)`(모듈에 별칭이 붙어도 추적), 그리고 `from time import sleep [as x]`
로 바인딩된 이름의 호출. 허용 목록은 없습니다 — 위반이 있으면 그 파일과 줄을 보고합니다.
"""

from __future__ import annotations

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

_SLEEP_MODULES = {"time", "asyncio"}

_SCAN_GLOBS = [
    "apps/*/tests/**/*.py",
    "packages/*/tests/**/*.py",
    "tests/**/*.py",
]


def _scan_files() -> list[Path]:
    files: set[Path] = set()
    for pattern in _SCAN_GLOBS:
        for path in REPO_ROOT.glob(pattern):
            if not path.is_file():
                continue
            if "fixtures" in path.relative_to(REPO_ROOT).parts:
                continue
            if "__pycache__" in path.parts:
                continue
            files.add(path)
    return sorted(files)


class _SleepCallFinder(ast.NodeVisitor):
    """한 파일의 AST 를 훑어 `time.sleep`/`asyncio.sleep` 호출 지점을 모읍니다.

    바인딩은 파일 전체(모든 스코프)에서 본 `import`/`from import` 문으로 정합니다 —
    이 검사의 목적은 "테스트가 sleep 으로 기다리는가" 이지 스코프 분석이 아니므로,
    함수 안에서 지역 import 를 해도 놓치지 않는 쪽(과탐 아님, 누락 방지)을 택합니다.
    """

    def __init__(self) -> None:
        self.module_aliases: dict[str, str] = {}  # 지역 이름 -> "time" | "asyncio"
        self.name_aliases: dict[str, str] = {}  # 지역 이름 -> "time.sleep" | "asyncio.sleep"
        self.violations: list[int] = []

    def visit_Import(self, node: ast.Import) -> None:  # noqa: N802 -- ast visitor 명명 규약
        for alias in node.names:
            if alias.name in _SLEEP_MODULES:
                self.module_aliases[alias.asname or alias.name] = alias.name
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:  # noqa: N802
        if node.module in _SLEEP_MODULES:
            for alias in node.names:
                if alias.name == "sleep":
                    self.name_aliases[alias.asname or alias.name] = f"{node.module}.sleep"
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:  # noqa: N802
        func = node.func
        if isinstance(func, ast.Attribute) and func.attr == "sleep":
            value = func.value
            if isinstance(value, ast.Name) and value.id in self.module_aliases:
                self.violations.append(node.lineno)
        elif isinstance(func, ast.Name) and func.id in self.name_aliases:
            self.violations.append(node.lineno)
        self.generic_visit(node)


def _find_sleep_calls(path: Path) -> list[int]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    finder = _SleepCallFinder()
    finder.visit(tree)
    return finder.violations


def test_no_time_or_asyncio_sleep_calls_in_test_trees() -> None:
    violations: list[str] = []
    for path in _scan_files():
        for lineno in _find_sleep_calls(path):
            violations.append(f"{path.relative_to(REPO_ROOT)}:{lineno}")

    assert not violations, (
        "sleep() 호출 금지(spec 0002 R-11) — tests/support/waiting.wait_until 나 시계 "
        f"주입을 쓰세요: {violations}"
    )
