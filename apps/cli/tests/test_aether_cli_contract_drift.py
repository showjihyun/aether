"""spec 0006 C-1, R-3: CLI 가 쓰는 경로·메서드가 `packages/sdk/openapi.json` 에 실재한다.

계약이 TS SDK 와 이 CLI 두 곳에서 구현되므로, 경로가 바뀌면 이 테스트가 먼저 실패한다.
"""

from __future__ import annotations

import json
import tomllib
from pathlib import Path

from aether_cli import contract

ROOT = Path(__file__).resolve().parents[3]
OPENAPI = ROOT / "packages" / "sdk" / "openapi.json"


def test_every_cli_endpoint_exists_in_openapi() -> None:
    """spec 0006 C-1: `contract.ALL_ENDPOINTS` 의 (메서드, 경로) 전부가 openapi 에 있다."""
    paths = json.loads(OPENAPI.read_text(encoding="utf-8"))["paths"]

    missing = [
        f"{e.method} {e.path}"
        for e in contract.ALL_ENDPOINTS
        if e.method.lower() not in paths.get(e.path, {})
    ]

    assert missing == [], f"openapi.json 에 없는 경로: {missing}"


def test_all_endpoints_lists_every_endpoint_constant() -> None:
    """상수를 하나 더하고 `ALL_ENDPOINTS` 에 빠뜨리면 드리프트 테스트가 그것을 보지 못한다."""
    declared = {v for v in vars(contract).values() if isinstance(v, contract.Endpoint)}

    assert declared == set(contract.ALL_ENDPOINTS)


def test_cli_source_has_no_path_literals_outside_contract() -> None:
    """경로를 문자열로 흩뿌리지 않는다: `contract.py` 밖에는 `"/agents`·`"/runs` 리터럴이 없다."""
    src = ROOT / "apps" / "cli" / "src" / "aether_cli"
    offenders = [
        p.name
        for p in src.glob("*.py")
        if p.name != "contract.py"
        and any(
            token in p.read_text(encoding="utf-8") for token in ('"/agents', '"/runs', "'/agents")
        )
    ]

    assert offenders == [], offenders


def test_cli_declares_no_runtime_dependencies() -> None:
    """spec 0006 R-3·D-1: `dependencies` 는 비어 있다(`httpx`·`requests`·`aiohttp` 없음)."""
    pyproject = tomllib.loads(
        (ROOT / "apps" / "cli" / "pyproject.toml").read_text(encoding="utf-8")
    )

    assert pyproject["project"]["dependencies"] == []
