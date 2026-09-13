"""spec 0002 D-13 (architecture.md 3.1 AR-10): 포트에 어댑터를 꽂는 조립은
`apps/*/src/aether_*/main.py` 한 곳뿐이어야 합니다 — `adapters.inbound` 와
`adapters.outbound` 를 **함께** import 하는 다른 모듈이 있으면 그 모듈이 조립을
하고 있다는 뜻입니다.

`.importlinter` 의 `layers`/`forbidden` 계약으로는 "main.py 만 예외" 라는 조건을
표현하기 어려워(임의의 한 모듈만 허용하는 계약이 없음) AST 로 직접 검사합니다
(architecture.md 3.1 "기계 판정").
"""

from __future__ import annotations

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

_SRC_GLOBS = [
    "apps/*/src/aether_*/**/*.py",
    "packages/*/src/aether_*/**/*.py",
]


def _package_name(path: Path) -> str | None:
    """`.../src/aether_xxx/...` 에서 `aether_xxx` 를 뽑습니다."""
    parts = path.parts
    if "src" not in parts:
        return None
    idx = parts.index("src")
    if idx + 1 >= len(parts):
        return None
    return parts[idx + 1]


def _imports_both_inbound_and_outbound_adapters(tree: ast.Module, package: str) -> bool:
    imports_inbound = False
    imports_outbound = False
    inbound_marker = f"{package}.adapters.inbound"
    outbound_marker = f"{package}.adapters.outbound"

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith(inbound_marker):
                    imports_inbound = True
                if alias.name.startswith(outbound_marker):
                    imports_outbound = True
        elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
            if node.module.startswith(inbound_marker):
                imports_inbound = True
            if node.module.startswith(outbound_marker):
                imports_outbound = True

    return imports_inbound and imports_outbound


def _violations() -> list[Path]:
    violations: list[Path] = []
    for pattern in _SRC_GLOBS:
        for path in REPO_ROOT.glob(pattern):
            if path.name in ("__init__.py", "main.py"):
                continue
            package = _package_name(path)
            if package is None:
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            if _imports_both_inbound_and_outbound_adapters(tree, package):
                violations.append(path)
    return violations


def test_real_repository_has_no_composition_outside_main_py() -> None:
    violations = _violations()
    assert not violations, (
        "adapters.inbound 와 adapters.outbound 를 함께 import 하는 모듈이 "
        f"main.py 밖에 있습니다: {[str(v.relative_to(REPO_ROOT)) for v in violations]}"
    )


def test_detects_a_module_combining_inbound_and_outbound_imports(tmp_path: Path) -> None:
    """자기 증명 — 검사 함수가 실제로 위반을 잡는지, 주입한 예시로 확인합니다."""
    bad_module = tmp_path / "not_main.py"
    bad_module.write_text(
        "from aether_api.adapters.inbound.http.agents import build_agents_router\n"
        "from aether_api.adapters.outbound.db.agent_repository import PostgresAgentRepository\n",
        encoding="utf-8",
    )
    tree = ast.parse(bad_module.read_text(encoding="utf-8"), filename=str(bad_module))

    assert _imports_both_inbound_and_outbound_adapters(tree, "aether_api")


def test_does_not_flag_a_module_importing_only_inbound_adapters(tmp_path: Path) -> None:
    """반증 — 한쪽만 import 하면 걸리지 않아야 합니다(오탐 방지)."""
    module = tmp_path / "router_only.py"
    module.write_text(
        "from aether_api.adapters.inbound.http.agents import build_agents_router\n",
        encoding="utf-8",
    )
    tree = ast.parse(module.read_text(encoding="utf-8"), filename=str(module))

    assert not _imports_both_inbound_and_outbound_adapters(tree, "aether_api")
