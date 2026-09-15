"""`openapi`·`events-schema`·`keys create` 서브커맨드의 함수만 둡니다.

실행 진입점은 `main.cli` 입니다 — `main` 을 import 하지 않습니다. `keys_create` 는
inbound 포트 `IssueApiKey` **타입**만 봅니다(AR-12) — 유스케이스 구현은 `main.py` 가
조립해 건네줍니다. `events_schema` 는 `aether_runtime.domain.events` **타입**만
봅니다 — api 는 `aether_runtime.domain` 을 import 할 수 있습니다(AR-7 확장, spec 0002
2.7 "스키마 소유").
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from aether_runtime.domain.events import PAYLOAD_MODELS, RunEvent
from fastapi import FastAPI

from aether_api.application.ports.inbound.issue_api_key import IssueApiKey

_EVENTS_SCHEMA_URI = "https://json-schema.org/draft/2020-12/schema"


def build_parser() -> argparse.ArgumentParser:
    """`aether-api openapi` / `aether-api events-schema` / `aether-api keys create
    --label` 의 argparse 정의."""
    parser = argparse.ArgumentParser(prog="aether-api")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("openapi", help="조립된 앱의 OpenAPI 스키마를 JSON 으로 stdout 에 출력")
    subparsers.add_parser(
        "events-schema", help="Run 이벤트 봉투·payload 8종의 JSON Schema 를 stdout 에 출력"
    )

    keys_parser = subparsers.add_parser("keys", help="API 키 관리")
    keys_subparsers = keys_parser.add_subparsers(dest="keys_command", required=True)
    create_parser = keys_subparsers.add_parser("create", help="새 API 키 발급")
    create_parser.add_argument("--label", required=True, help="키를 구분할 이름")

    return parser


def openapi(app: FastAPI) -> None:
    """조립된 `FastAPI` 앱의 OpenAPI 스키마를 JSON 으로 stdout 에 출력합니다.

    P0-3 의 `packages/sdk` 생성과 드리프트 테스트가 이 출력에 기댑니다.
    """
    schema = app.openapi()
    sys.stdout.write(json.dumps(schema, ensure_ascii=False, indent=2) + "\n")


def _events_schema_payload() -> dict[str, Any]:
    """`RunEvent`·8종 payload 의 JSON Schema 를 하나의 문서로 모읍니다(spec 0002 2.7).

    `$defs` 의 키 순서는 `PAYLOAD_MODELS` dict 순서를 따르지만, 출력 시 `sort_keys=True`
    를 쓰므로 최종 stdout 은 dict 순서와 무관하게 결정적입니다.

    최상위 문서 자체가 `"$ref": "#/$defs/RunEvent"` 를 갖습니다 — JSON Schema
    2020-12 는 `$ref` 옆의 형제 키워드(`title`·`$defs`·`x-aether-event-types`)를
    무시하지 않으므로(draft-07 과 달리) 문서 형태는 그대로 두면서, `json2ts` 가
    `$ref` 를 따라가 `RunEvent` 인터페이스를 필드까지 채워서(제네릭 `{[k: string]:
    unknown}` 대신) 생성하게 합니다 — 이 `$ref` 가 없으면 최상위 스키마에
    `type`/`properties` 가 없어(순수 `$defs` 컨테이너) `json2ts` 가 아무 필드도 없는
    빈 인터페이스만 냅니다(확인함).
    """
    payload_defs = {model.__name__: model.model_json_schema() for model in PAYLOAD_MODELS.values()}
    return {
        "$schema": _EVENTS_SCHEMA_URI,
        "title": "RunEvent",
        "$ref": "#/$defs/RunEvent",
        "$defs": {"RunEvent": RunEvent.model_json_schema(), **payload_defs},
        "x-aether-event-types": {
            event_type: model.__name__ for event_type, model in PAYLOAD_MODELS.items()
        },
    }


def events_schema() -> None:
    """`aether_runtime.domain.events` 로부터 결정적 JSON Schema 를 stdout 에 출력합니다.

    `packages/sdk/events.schema.json` 커밋과 `json2ts` 타입 생성(P1-6)의 근거입니다
    (R-12 드리프트 검사 대상).
    """
    schema = _events_schema_payload()
    sys.stdout.write(json.dumps(schema, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def keys_create(issue: IssueApiKey, label: str) -> None:
    """새 키를 발급해 stdout 에 원문 **한 줄만**, stderr 에 메타데이터(id·label)를 씁니다.

    원문은 이 한 곳에서만, 이 한 번만 나갑니다(spec 2.9 발급 행) — stderr 에도, 다른 어떤
    로그에도 원문을 남기지 않습니다.
    """
    issued = issue(label)
    sys.stdout.write(issued.raw_key + "\n")
    sys.stderr.write(f"id={issued.key.id} label={issued.key.label}\n")
