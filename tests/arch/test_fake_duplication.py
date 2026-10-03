"""improvement-log 2026-09-28-001: 포트의 fake 가 `tests/support/` 밖에
복제되면 포트 메서드 하나가 늘 때마다 그 복제본 전부를 기계적으로 고쳐야
한다(P2-6 에서 39 failed, 반복 예산 초과). 이 테스트는 그 재발을 구조적으로
막는다.

grep 기반 검사는 docstring 안의 클래스 이름("`FakeMcpClient` 를 쓴다" 같은
문장)을 오탐한다 — 직전 단위에서 실제로 그 오탐이 났다(`test_no_sleep_in_tests.py`
의 설계 이유와 같다). 그래서 **`ast`** 로 각 파일의 최상위 `ClassDef` 이름만
모아 판정한다.

이름 규칙은 fake 를 가리키는 접두어로 좁게 둔다 — `Fake*`·`InMemory*`·
`Noop*`·`Stub*`·`_Single*`·`_Fake*`. 이 접두어들은 이미 저장소 전체 테스트가
실제로 쓰는 명명 관례다(`packages/runtime/tests/fakes.py`·
`apps/api/tests/fakes.py` 의 `Fake*`/`InMemory*`, `_SingleToolGateway`,
`test_execute_run_gateway_integration.py` 의 `_FakeMcpClient` 등). 이 접두어
밖의 이름(`_FakeClient`, `AllowJudge` 등)은 이번 판정 대상이 아니다 — 그런
이름까지 넓히면 이번 범위 밖의 다른 중복(예: `FakeAuditSink`)까지 걸려
blast radius 가 커진다(사람 판단으로 범위를 좁혔다).

같은 이름의 클래스가 `tests/support/` **밖에** 둘 이상(파일이 다른 두 곳)
정의되면 실패한다. 그리고 `tests/support/` 가 가진 이름을 밖에서 다시 정의하는
것도 실패한다 — 그 재정의는 import 를 **가려서**(shadowing) 공용 fake 를 쓰는
것처럼 보이면서 실제로는 옛 구현을 쓰게 만든다. 이 규칙은 실측으로 왔다:
2026-10-03 에 통합 테스트가 import 를 추가하고 자기 파일의 옛 정의를 남겨 두어
`TypeError: FakeMcpClient() takes no arguments` 로 두 테스트가 깨졌고, 그때의
약한 규칙("밖에 둘 이상")은 그것을 통과시켰다. `tests/support/` 안에서의 재정의는
허용 대상이 아니다 — 이 저장소에는 그런 경우가 없고, 생기면 그때 범위를
넓힌다.
"""

from __future__ import annotations

import ast
from collections import defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

_FAKE_PREFIXES = ("Fake", "InMemory", "Noop", "Stub", "_Single", "_Fake")

_SCAN_GLOBS = [
    "apps/*/tests/**/*.py",
    "packages/*/tests/**/*.py",
    "tests/**/*.py",
]

_SUPPORT_DIR = REPO_ROOT / "tests" / "support"


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


def _is_fake_name(name: str) -> bool:
    return any(name.startswith(prefix) for prefix in _FAKE_PREFIXES)


def _top_level_fake_class_names(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    return [
        node.name
        for node in tree.body
        if isinstance(node, ast.ClassDef) and _is_fake_name(node.name)
    ]


def test_fake_classes_are_not_duplicated_outside_tests_support() -> None:
    support_names: set[str] = set()
    locations: dict[str, list[Path]] = defaultdict(list)
    for path in _scan_files():
        names = _top_level_fake_class_names(path)
        if path.is_relative_to(_SUPPORT_DIR):
            support_names.update(names)
            continue
        for name in names:
            locations[name].append(path)

    duplicates = {name: paths for name, paths in locations.items() if len(paths) > 1}
    shadowing = {name: paths for name, paths in locations.items() if name in support_names}

    offenders = {
        name: [str(p.relative_to(REPO_ROOT)) for p in paths]
        for name, paths in {**duplicates, **shadowing}.items()
    }
    assert not offenders, (
        "같은 포트의 fake 는 tests/support/ 아래 한 곳으로 모으세요 — "
        "밖에서 둘 이상 정의하거나, tests/support/ 의 이름을 밖에서 다시 정의하면(가림) "
        f"실패합니다(improvement-log 2026-09-28-001): {offenders}"
    )
