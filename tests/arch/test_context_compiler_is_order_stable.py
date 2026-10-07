"""`aether_context` 의 조립 경로가 순서 불안정한 자료구조를 쓰지 않는다.

근거: spec 0004 R-1·D-12 는 "같은 입력에 같은 출력" 을 요구한다. 그 요구를 100회 반복
테스트로만 고정하면 **같은 프로세스 안에서만** 증명된다 — 2026-10-07 에 실측으로 확인했다.
`messages.extend(sorted(set(...), key=hash))` 를 주입했더니 100회 반복 결정성 테스트는
**통과했고**(한 프로세스 안에서 `hash()` 는 안정적이다) D-7 순서 테스트만 실패했다.
즉 해시 시드에 의존하는 순서는 반복 실행으로 드러나지 않는다.

그래서 구조로 고정한다 — 조립 경로에 `set(`·`frozenset(`·`.values()`·`.items()`·`.keys()`
순회가 없어야 한다. 정렬된 순회가 필요하면 `sorted(...)` 를 명시적으로 쓴다(그 경우
`sorted` 호출이 보이므로 이 테스트가 통과한다).

이 규칙은 `aether_context` 의 `application` 과 `domain` 에만 적용한다. 어댑터는 외부
자료구조를 다루므로 예외이고, 그 출력이 조립에 들어갈 때는 포트 타입(`tuple`)으로 좁혀진다.
"""

from __future__ import annotations

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCANNED = (
    REPO_ROOT / "packages" / "context" / "src" / "aether_context" / "application",
    REPO_ROOT / "packages" / "context" / "src" / "aether_context" / "domain",
)
_FORBIDDEN_CALLS = frozenset({"set", "frozenset"})
_FORBIDDEN_METHODS = frozenset({"values", "items", "keys"})


def _python_files() -> list[Path]:
    files: list[Path] = []
    for root in SCANNED:
        files.extend(p for p in root.rglob("*.py") if "__pycache__" not in p.parts)
    return sorted(files)


def _offenders(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Name) and func.id in _FORBIDDEN_CALLS:
            found.append(f"{path.name}:{node.lineno} {func.id}()")
        elif isinstance(func, ast.Attribute) and func.attr in _FORBIDDEN_METHODS:
            # sorted(d.items()) 처럼 정렬로 감싼 것은 허용한다 — 부모가 sorted 인지 본다.
            found.append(f"{path.name}:{node.lineno} .{func.attr}()")
    return found


def _sorted_wrapped_lines(path: Path) -> set[int]:
    """`sorted(...)` 의 인자 안에서 일어나는 호출의 줄 번호."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    wrapped: set[int] = set()
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "sorted"
        ):
            for inner in ast.walk(node):
                if isinstance(inner, ast.Call):
                    wrapped.add(inner.lineno)
    return wrapped


def test_context_assembly_has_no_order_unstable_iteration() -> None:
    """조립 경로에 set·정렬 없는 매핑 순회가 없다."""
    offenders: dict[str, list[str]] = {}
    for path in _python_files():
        wrapped = _sorted_wrapped_lines(path)
        bad = [o for o in _offenders(path) if int(o.split(":")[1].split(" ")[0]) not in wrapped]
        if bad:
            offenders[str(path.relative_to(REPO_ROOT))] = bad

    assert not offenders, (
        "Context 조립은 순서가 안정적이어야 합니다(spec 0004 R-1·D-12). "
        "set·frozenset·정렬 없는 매핑 순회를 쓰지 마십시오 — 필요하면 sorted(...) 로 "
        f"감싸십시오. 100회 반복 테스트는 이 부류를 잡지 못합니다: {offenders}"
    )
