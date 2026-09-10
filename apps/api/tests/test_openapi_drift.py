"""드리프트 1 (api ↔ openapi.json, spec 2.4): api 가 지금 내보내는 OpenAPI 스키마가
커밋된 `packages/sdk/openapi.json` 과 같은지 **파싱해서** 비교합니다.

subprocess 로 CLI 를 다시 실행하지 않고 in-process 로 `app.openapi()` 를 직접 부릅니다.
텍스트 비교는 키 순서·공백에 깨지므로 JSON 으로 파싱한 뒤 비교합니다.
"""

from __future__ import annotations

import json
from pathlib import Path

from aether_api.main import app

REPO_ROOT = Path(__file__).resolve().parents[3]
COMMITTED_OPENAPI_PATH = REPO_ROOT / "packages" / "sdk" / "openapi.json"


def test_committed_openapi_json_matches_the_apps_current_schema() -> None:
    committed = json.loads(COMMITTED_OPENAPI_PATH.read_text(encoding="utf-8"))

    current = app.openapi()

    assert current == committed
