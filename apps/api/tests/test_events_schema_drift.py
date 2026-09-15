"""spec 0002 R-12: api 가 지금 내보내는 이벤트 JSON Schema 가 커밋된
`packages/sdk/events.schema.json` 과 같은지 파싱해서 비교합니다.

`test_openapi_drift.py` 와 같은 이유로 텍스트가 아니라 JSON 으로 파싱해 비교합니다 —
키 순서·공백 차이에 깨지지 않게 하기 위해서입니다. CLI 를 subprocess 로 다시 실행하지
않고 `_events_schema_payload()` 를 in-process 로 부릅니다.
"""

from __future__ import annotations

import json
from pathlib import Path

from aether_api.adapters.inbound.cli import _events_schema_payload

REPO_ROOT = Path(__file__).resolve().parents[3]
COMMITTED_EVENTS_SCHEMA_PATH = REPO_ROOT / "packages" / "sdk" / "events.schema.json"


def test_committed_events_schema_json_matches_the_apps_current_schema() -> None:
    committed = json.loads(COMMITTED_EVENTS_SCHEMA_PATH.read_text(encoding="utf-8"))

    current = _events_schema_payload()

    assert current == committed
