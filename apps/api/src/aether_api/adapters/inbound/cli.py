"""`openapi` 서브커맨드의 함수만 둡니다.

실행 진입점은 `main.cli` 입니다 — `main` 을 import 하지 않습니다.
"""

from __future__ import annotations

import argparse
import json
import sys

from fastapi import FastAPI


def build_parser() -> argparse.ArgumentParser:
    """`aether-api openapi` 서브커맨드의 argparse 정의."""
    parser = argparse.ArgumentParser(prog="aether-api")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("openapi", help="조립된 앱의 OpenAPI 스키마를 JSON 으로 stdout 에 출력")
    return parser


def openapi(app: FastAPI) -> None:
    """조립된 `FastAPI` 앱의 OpenAPI 스키마를 JSON 으로 stdout 에 출력합니다.

    P0-3 의 `packages/sdk` 생성과 드리프트 테스트가 이 출력에 기댑니다.
    """
    schema = app.openapi()
    sys.stdout.write(json.dumps(schema, ensure_ascii=False, indent=2) + "\n")
