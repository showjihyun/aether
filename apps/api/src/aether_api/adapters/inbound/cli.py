"""`openapi`·`keys create` 서브커맨드의 함수만 둡니다.

실행 진입점은 `main.cli` 입니다 — `main` 을 import 하지 않습니다. `keys_create` 는
inbound 포트 `IssueApiKey` **타입**만 봅니다(AR-12) — 유스케이스 구현은 `main.py` 가
조립해 건네줍니다.
"""

from __future__ import annotations

import argparse
import json
import sys

from fastapi import FastAPI

from aether_api.application.ports.inbound.issue_api_key import IssueApiKey


def build_parser() -> argparse.ArgumentParser:
    """`aether-api openapi` / `aether-api keys create --label` 의 argparse 정의."""
    parser = argparse.ArgumentParser(prog="aether-api")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("openapi", help="조립된 앱의 OpenAPI 스키마를 JSON 으로 stdout 에 출력")

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


def keys_create(issue: IssueApiKey, label: str) -> None:
    """새 키를 발급해 stdout 에 원문 **한 줄만**, stderr 에 메타데이터(id·label)를 씁니다.

    원문은 이 한 곳에서만, 이 한 번만 나갑니다(spec 2.9 발급 행) — stderr 에도, 다른 어떤
    로그에도 원문을 남기지 않습니다.
    """
    issued = issue(label)
    sys.stdout.write(issued.raw_key + "\n")
    sys.stderr.write(f"id={issued.key.id} label={issued.key.label}\n")
