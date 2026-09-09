"""`aether_api.adapters.inbound.cli.openapi` 계약 테스트: stdout 에 유효한 JSON, `/healthz` 포함."""

from __future__ import annotations

import json

import pytest
from aether_api.adapters.inbound.cli import openapi
from aether_api.main import create_app
from aether_api.settings import Settings


def test_openapi_writes_valid_json_with_healthz_path(
    capsys: pytest.CaptureFixture[str],
) -> None:
    app = create_app(Settings())

    openapi(app)

    captured = capsys.readouterr()
    schema = json.loads(captured.out)
    assert "/healthz" in schema["paths"]
