"""`openapi`·`events-schema`·`keys create`·`agents get-version` 서브커맨드의 함수만 둡니다.

실행 진입점은 `main.cli` 입니다 — `main` 을 import 하지 않습니다. `keys_create` 는
inbound 포트 `IssueApiKey` **타입**만 봅니다(AR-12) — 유스케이스 구현은 `main.py` 가
조립해 건네줍니다. `events_schema` 는 `aether_runtime.domain.events` **타입**만
봅니다 — api 는 `aether_runtime.domain` 을 import 할 수 있습니다(AR-7 확장, spec 0002
2.7 "스키마 소유"). `agents_get_version` 은 inbound 포트 `GetAgentVersion` **타입**만
봅니다(AR-12) — HTTP 라우터(`adapters/inbound/http/agents.py`)의 `GET
/agents/{id}/versions/{version}` 과 같은 포트에 붙은 두 번째 inbound 어댑터입니다
(architecture.md 3.1 "방향과 신뢰 경계").
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any
from uuid import UUID

from aether_runtime.domain.events import PAYLOAD_MODELS, RunEvent
from fastapi import FastAPI

from aether_api.application.ports.inbound.agents import GetAgentVersion
from aether_api.application.ports.inbound.issue_api_key import IssueApiKey
from aether_api.domain.agent import AgentNotFound, AgentVersionNotFound

_EVENTS_SCHEMA_URI = "https://json-schema.org/draft/2020-12/schema"


def build_parser() -> argparse.ArgumentParser:
    """`aether-api openapi` / `aether-api events-schema` / `aether-api keys create
    --label` / `aether-api agents get-version --agent-id --version` 의 argparse 정의."""
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

    agents_parser = subparsers.add_parser("agents", help="Agent Registry 조회")
    agents_subparsers = agents_parser.add_subparsers(dest="agents_command", required=True)
    get_version_parser = agents_subparsers.add_parser(
        "get-version", help="특정 Agent Version 의 정의(AgentDefinition)를 JSON 으로 stdout 에 출력"
    )
    get_version_parser.add_argument("--agent-id", required=True, type=UUID, help="Agent 의 UUID")
    get_version_parser.add_argument("--version", required=True, type=int, help="버전 번호")

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


def agents_get_version(get_agent_version: GetAgentVersion, agent_id: UUID, version: int) -> None:
    """특정 Agent Version 의 `definition`(`AgentDefinition`)만 JSON 으로 stdout 에 출력합니다.

    `keys_create` 와 같은 분리를 따릅니다 — 자동화가 파이프로 받는 stdout 에는 정의
    하나만 싣고, 메타데이터(`agent_id`·`version`·`created_at`)는 stderr 에 씁니다.
    Agent 나 버전이 없으면 HTTP 라우터(`GET /agents/{id}/versions/{version}`)와 같은
    오류 코드(spec 0002 2.2)를 stderr 에 쓰고 종료 코드 1 로 끝냅니다 — 값 없이 빈 JSON
    을 stdout 에 내보내면 호출자가 실패를 성공으로 오인합니다.
    """
    try:
        agent_version = get_agent_version(agent_id, version)
    except AgentNotFound:
        sys.stderr.write("error: agent_not_found\n")
        raise SystemExit(1) from None
    except AgentVersionNotFound:
        sys.stderr.write("error: agent_version_not_found\n")
        raise SystemExit(1) from None

    definition_json = agent_version.definition.model_dump(mode="json")
    sys.stdout.write(json.dumps(definition_json, ensure_ascii=False, indent=2) + "\n")
    sys.stderr.write(
        f"agent_id={agent_version.agent_id} version={agent_version.version} "
        f"created_at={agent_version.created_at.isoformat()}\n"
    )
