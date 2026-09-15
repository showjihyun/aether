"""spec 0002 2.7, D-4: `aether_api.adapters.inbound.cli.events_schema` 계약 테스트.

`aether_runtime.domain.events` 의 `RunEvent`·8종 payload 로부터 pydantic JSON Schema 를
stdout 에 **결정적**(키 정렬, 들여쓰기 2)으로 냅니다 — `$defs.RunEvent`, `$defs.<PayloadClass>`
8개, `x-aether-event-types` 매핑. `packages/sdk/events.schema.json` 커밋과
`json2ts` 타입 생성의 근거가 됩니다(R-12).
"""

from __future__ import annotations

import json

import pytest
from aether_api.adapters.inbound.cli import events_schema
from aether_runtime.domain.events import EVENT_TYPES, PAYLOAD_MODELS


def test_events_schema_writes_valid_deterministic_json(
    capsys: pytest.CaptureFixture[str],
) -> None:
    events_schema()
    first = capsys.readouterr().out

    events_schema()
    second = capsys.readouterr().out

    assert first == second, "events-schema 출력은 실행마다 바이트 단위로 같아야 합니다(결정성)"

    schema = json.loads(first)
    assert schema["title"] == "RunEvent"
    assert "$schema" in schema
    assert set(schema["$defs"]) == {"RunEvent"} | {
        model.__name__ for model in PAYLOAD_MODELS.values()
    }
    assert set(schema["x-aether-event-types"]) == EVENT_TYPES
    for event_type, class_name in schema["x-aether-event-types"].items():
        assert class_name == PAYLOAD_MODELS[event_type].__name__


def test_events_schema_output_is_indented_with_sorted_keys(
    capsys: pytest.CaptureFixture[str],
) -> None:
    events_schema()
    out = capsys.readouterr().out

    schema = json.loads(out)
    reserialized = json.dumps(schema, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    assert out == reserialized
