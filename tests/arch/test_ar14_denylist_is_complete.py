"""AR-14 의 금지 목록이 **제품 패키지 전부**를 담고 있는지 (spec 0006 D-2).

AR-14 는 `forbidden_modules` 에 패키지 이름을 **손으로 적는** denylist 입니다 —
import-linter 에 와일드카드가 없어서 다른 방법이 없습니다. 그 구조의 결함은 분명합니다:
새 제품 패키지가 생기고 목록에 더하지 않으면 **CLI 가 그것을 import 해도 계약이
침묵합니다.** 2026-10-17 에 실제로 `aether_evaluation` 이 빠져 있었고(배경 보안 리뷰가
`incomplete-denylist` 로 지적), 그래서 완전성을 기억에 맡기지 않고 여기서 고정합니다.

판정 방식: 워크스페이스 멤버(`pyproject.toml` 의 `[tool.uv.workspace] members`)에서
패키지 이름을 유도하고, `apps/cli` 자신을 뺀 나머지가 AR-14 의 금지 목록에 **전부**
있는지 봅니다. 새 패키지를 추가하면 **이 테스트가 먼저 실패**하므로 목록을 잊을 수
없습니다.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
_CONTRACT = "ar14-cli-does-not-import-product"
_CLI_PACKAGE = "aether_cli"


def _workspace_product_packages() -> set[str]:
    """워크스페이스 멤버의 import 이름 — CLI 자신은 제외합니다."""
    data = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    members: list[str] = data["tool"]["uv"]["workspace"]["members"]
    names = {f"aether_{Path(member).name}" for member in members}
    return names - {_CLI_PACKAGE}


def _forbidden_modules_of_ar14() -> set[str]:
    """`.importlinter` 의 AR-14 블록에서 `forbidden_modules` 를 읽습니다.

    `configparser` 를 쓰지 않고 줄 단위로 읽는 이유: 이 파일은 같은 키(`source_modules`)를
    여러 계약에서 쓰고, 값이 들여쓴 여러 줄입니다. 파싱 규칙을 늘리는 대신 블록만 좁혀
    읽습니다.
    """
    lines = (REPO_ROOT / ".importlinter").read_text(encoding="utf-8").splitlines()
    start = next(
        i for i, line in enumerate(lines) if line.strip() == f"[importlinter:contract:{_CONTRACT}]"
    )
    modules: set[str] = set()
    in_forbidden = False
    for line in lines[start + 1 :]:
        if line.startswith("["):
            break
        if line.startswith("forbidden_modules"):
            in_forbidden = True
            continue
        if in_forbidden:
            if line.startswith((" ", "\t")) and line.strip():
                modules.add(line.strip())
            elif line.strip():
                in_forbidden = False
    return modules


def test_ar14_forbids_every_product_package() -> None:
    expected = _workspace_product_packages()
    forbidden = _forbidden_modules_of_ar14()

    missing = expected - forbidden
    assert not missing, (
        f"AR-14 의 금지 목록에 빠진 제품 패키지가 있습니다: {sorted(missing)}. "
        "`.importlinter` 의 그 계약에 더하십시오 — 빠지면 CLI 가 그것을 import 해도 "
        "계약이 침묵합니다(보호 파일이므로 사람이 커밋합니다)."
    )


def test_ar14_does_not_forbid_the_cli_itself_or_unknown_names() -> None:
    """목록이 **부풀지도** 않는지 — 없는 패키지를 적으면 오타를 알 수 없습니다."""
    expected = _workspace_product_packages()
    forbidden = _forbidden_modules_of_ar14()

    assert _CLI_PACKAGE not in forbidden, "CLI 자신을 금지하면 계약이 자기 모듈을 막습니다"
    unknown = forbidden - expected
    assert not unknown, f"AR-14 에 워크스페이스에 없는 이름이 있습니다(오타?): {sorted(unknown)}"
