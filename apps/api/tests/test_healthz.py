"""`GET /healthz` 계약 테스트(spec 2.3): 200, 기본 버전 `dev`, env override, OpenAPI 등록."""

from __future__ import annotations

import pytest
from aether_api.main import create_app
from aether_api.settings import Settings
from fastapi.testclient import TestClient


def test_healthz_returns_ok_with_default_version() -> None:
    client = TestClient(create_app(Settings()))

    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "api", "version": "dev"}


def test_healthz_reflects_aether_version_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AETHER_VERSION", "1.2.3")
    client = TestClient(create_app(Settings()))

    response = client.get("/healthz")

    assert response.json()["version"] == "1.2.3"


def test_healthz_registered_in_openapi_schema_with_response_model() -> None:
    app = create_app(Settings())

    schema = app.openapi()

    assert "/healthz" in schema["paths"]
    responses = schema["paths"]["/healthz"]["get"]["responses"]
    assert "200" in responses
    response_schema = responses["200"]["content"]["application/json"]["schema"]
    assert "$ref" in response_schema
