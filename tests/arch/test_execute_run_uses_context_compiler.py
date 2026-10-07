"""spec 0004 R-3 (P3-1): `execute_run.py` 가 모델 입력을 직접 조립하지 않고
`ContextCompiler` 포트를 지나는지를 AST 로 판정합니다.

문자열 검색(`"Message("` in text)은 docstring 의 설명 문장(예: 이 파일 자체의
`Message(...)` 용례를 설명하는 문장)에 오탐합니다 — 직전 라운드에 그 오탐이 실제로
났습니다. 그래서 AST 로 **실제 호출 표현식**만 봅니다: `Message(` 처럼 `Message`
이름을 직접 호출하는 `ast.Call` 이 0건이어야 합니다. `Message.user(...)` 같은
분류 메서드 호출(`ast.Attribute`)은 이 판정 대상이 아닙니다 — `domain.run.Message`
의 팩토리이고, 거기서만 실제 생성자를 부릅니다.
"""

from __future__ import annotations

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
EXECUTE_RUN = (
    REPO_ROOT
    / "packages"
    / "runtime"
    / "src"
    / "aether_runtime"
    / "application"
    / "usecases"
    / "execute_run.py"
)


def _direct_message_constructor_calls(tree: ast.Module) -> list[ast.Call]:
    calls = []
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "Message"
        ):
            calls.append(node)
    return calls


def test_execute_run_has_zero_direct_message_constructor_calls() -> None:
    tree = ast.parse(EXECUTE_RUN.read_text(encoding="utf-8"))
    calls = _direct_message_constructor_calls(tree)
    assert calls == [], (
        f"execute_run.py 에 직접 `Message(...)` 생성자 호출이 {len(calls)}건 있습니다"
        f" (줄: {[c.lineno for c in calls]}) — `Message.system/user/assistant/tool(...)`"
        " 팩토리나 `ContextCompiler` 호출로 바꾸십시오."
    )


def test_execute_run_imports_context_compiler_port() -> None:
    """R-3: Executor 가 `ContextCompiler` outbound 포트를 실제로 쓰는지(단순
    존재가 아니라 import 되어 있는지)."""
    tree = ast.parse(EXECUTE_RUN.read_text(encoding="utf-8"))
    imported_names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module is not None:
            if node.module.endswith("ports.outbound.context_compiler"):
                imported_names.update(alias.name for alias in node.names)
    assert "ContextCompiler" in imported_names
