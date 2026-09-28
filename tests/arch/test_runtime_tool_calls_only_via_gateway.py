"""spec 0003 2.1, R-6 (P2-3): `aether_runtime` 에 `ToolGateway` 밖의 도구 호출
경로가 없는지를 구조로 판정합니다.

Phase 1(P1-4)의 `ToolRegistry`/`InMemoryToolRegistry`/`ClockTool`/`CalculatorTool`
는 이 단위에서 지웠습니다(D-5) — 같은 도구를 두 경로로 부를 수 있는 상태를 남기지
않기 위해서입니다. 이 테스트는 그 이름들이 `aether_runtime` 소스에 다시 나타나지
않는지, 그리고 `ExecuteRunUseCase` 가 도구를 부르는 자리(`self._tools.*`)가
`discover`·`call`(`ToolGateway` 포트의 메서드) 뿐인지를 AST 로 확인합니다.
"""

from __future__ import annotations

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
RUNTIME_SRC = REPO_ROOT / "packages" / "runtime" / "src" / "aether_runtime"
EXECUTE_RUN = RUNTIME_SRC / "application" / "usecases" / "execute_run.py"

_FORBIDDEN_NAMES = (
    "ToolRegistry",
    "InMemoryToolRegistry",
    "ClockTool",
    "CalculatorTool",
)

_ALLOWED_TOOLS_ATTR_METHODS = {"discover", "call"}


def _defined_or_referenced_names(tree: ast.Module) -> set[str]:
    """코드로 쓰인 식별자만 모읍니다 — docstring·주석의 설명 문장은 대상이 아닙니다."""
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, ast.Attribute):
            names.add(node.attr)
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                names.add(alias.asname or alias.name)
        elif isinstance(node, ast.ClassDef):
            names.add(node.name)
    return names


def test_deleted_phase1_tool_registry_names_do_not_reappear_in_runtime_src() -> None:
    offenders: list[str] = []
    for path in RUNTIME_SRC.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        used = _defined_or_referenced_names(tree)
        for name in _FORBIDDEN_NAMES:
            if name in used:
                offenders.append(f"{path.relative_to(REPO_ROOT)}: {name}")
    assert not offenders, f"Phase 1 의 ToolRegistry 계열 이름이 다시 나타났습니다: {offenders}"


def test_no_tool_gateway_adapter_directory_named_tools_remains() -> None:
    """`adapters/outbound/tools/`(구 레지스트리 자리)가 지워졌는지 — 같은 도구를
    두 경로로 부를 수 있는 상태를 남기지 않습니다(plan 0003 P2-3 주의)."""
    assert not (RUNTIME_SRC / "adapters" / "outbound" / "tools").exists()
    assert not (RUNTIME_SRC / "application" / "ports" / "outbound" / "tools.py").exists()
    assert (RUNTIME_SRC / "application" / "ports" / "outbound" / "tool_gateway.py").exists()
    assert (RUNTIME_SRC / "adapters" / "outbound" / "tool_gateway" / "mcp.py").exists()


def test_execute_run_only_calls_tool_gateway_discover_and_call() -> None:
    """`self._tools.<attr>` 형태의 접근이 `discover`/`call` 뿐입니다 — Gateway 포트
    밖의 메서드(옛 `get`/`names` 등)를 부르지 않습니다."""
    tree = ast.parse(EXECUTE_RUN.read_text(encoding="utf-8"), filename=str(EXECUTE_RUN))
    accessed: set[str] = set()
    # `self._tools.<name>` 패턴만 정확히 찾습니다.
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Attribute):
            inner = node.value
            if (
                isinstance(inner.value, ast.Name)
                and inner.value.id == "self"
                and inner.attr == "_tools"
            ):
                accessed.add(node.attr)

    assert accessed, "self._tools.<attr> 접근을 찾지 못했습니다 — 검사 로직을 확인하십시오"
    extra = accessed - _ALLOWED_TOOLS_ATTR_METHODS
    assert not extra, f"ToolGateway 포트 밖의 메서드가 호출되고 있습니다: {extra}"
