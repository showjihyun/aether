"""spec 0001 R-9 · 2.9 · AR-12 (H-3 설계 검토): `require_principal` HTTP 의존성.

**제품 코드에 새 보호 엔드포인트를 만들지 않습니다** — 이 파일 안에서만 테스트용
라우트(`/_test/protected`)를 등록합니다. Phase 1 의 `POST /agents` 가 첫 실제 보호
경로입니다.

설계: `require_principal(authenticate: Authenticate) -> Callable[..., Principal]` 이
`Authenticate` **포트 타입**만 받아 FastAPI `Depends` 로 쓸 콜러블을 만듭니다
(AR-12 — 어댑터는 유스케이스가 아니라 포트만 봅니다). `Authorization` 스킴 비교는
대소문자 무시(RFC 7235). 실패 사유는 WARNING 로그에만 남고 응답 본문에는 없습니다.

의도적으로 `from __future__ import annotations` 을 쓰지 않습니다 — 아래
`_client_with_protected_route` 가 테스트마다 다른 `authenticate` 클로저를 캡처한
`Annotated[Principal, Depends(...)]` 를 라우트 파라미터 타입으로 씁니다. 애노테이션이
지연 문자열이 되면(PEP 563) FastAPI 가 그 문자열을 함수의 모듈 전역에서만 `eval` 하므로
클로저 지역 변수인 `authenticate` 를 찾지 못해 그 의존성이 조용히 무시되고 422 가
납니다(직접 재현해 확인). 즉시 평가라 이 문제가 없습니다.
"""

import logging
from typing import Annotated
from uuid import uuid4

import pytest
from aether_api.adapters.inbound.http.auth import require_principal
from aether_api.application.ports.inbound.authenticate import Authenticate
from aether_api.application.usecases.authenticate import AuthenticateUseCase
from aether_api.domain.api_key import Principal, Unauthenticated, generate_raw_key
from aether_api.main import create_app
from aether_api.settings import Settings
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from apps.api.tests.fakes import FakeApiKeyStore


class _FakeAuthenticate:
    """`Authenticate` 포트의 최소 fake — `"good-key"` 만 통과시킵니다."""

    def __call__(self, raw_key: str | None) -> Principal:
        if raw_key == "good-key":
            return Principal(key_id=uuid4(), label="test-principal")
        raise Unauthenticated("bad key")


def _client_with_protected_route(authenticate: Authenticate) -> TestClient:
    app: FastAPI = create_app(Settings())
    dependency = Annotated[Principal, Depends(require_principal(authenticate))]

    @app.get("/_test/protected")
    def _protected(principal: dependency) -> dict[str, str]:
        return {"label": principal.label}

    return TestClient(app)


def test_missing_header_is_401_with_www_authenticate() -> None:
    client = _client_with_protected_route(_FakeAuthenticate())

    response = client.get("/_test/protected")

    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"


def test_malformed_header_is_401() -> None:
    client = _client_with_protected_route(_FakeAuthenticate())

    response = client.get("/_test/protected", headers={"Authorization": "not-bearer garbage"})

    assert response.status_code == 401


def test_wrong_key_is_401() -> None:
    client = _client_with_protected_route(_FakeAuthenticate())

    response = client.get("/_test/protected", headers={"Authorization": "Bearer bad-key"})

    assert response.status_code == 401


def test_valid_key_is_200_with_principal_label() -> None:
    client = _client_with_protected_route(_FakeAuthenticate())

    response = client.get("/_test/protected", headers={"Authorization": "Bearer good-key"})

    assert response.status_code == 200
    assert response.json() == {"label": "test-principal"}


def test_healthz_requires_no_header() -> None:
    client = _client_with_protected_route(_FakeAuthenticate())

    response = client.get("/healthz")

    assert response.status_code == 200


def test_lowercase_bearer_scheme_is_200() -> None:
    """spec 2.9 H-3: `Authorization` 스킴 비교는 대소문자 무시(RFC 7235)."""
    client = _client_with_protected_route(_FakeAuthenticate())

    response = client.get("/_test/protected", headers={"Authorization": "bearer good-key"})

    assert response.status_code == 200


def test_unregistered_key_logs_reason_without_raw_key_and_returns_generic_body(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """spec 2.9 H-3: 실패 사유는 WARNING 로그에만, 원문은 어디에도 없음, 본문은 고정 문구.

    실제 `AuthenticateUseCase`(fake store)를 꽂아 형식은 맞지만 미등록인 키로 요청합니다.
    """
    store = FakeApiKeyStore()
    authenticate = AuthenticateUseCase(store)
    client = _client_with_protected_route(authenticate)
    raw = generate_raw_key()

    with caplog.at_level(logging.WARNING):
        response = client.get("/_test/protected", headers={"Authorization": f"Bearer {raw}"})

    assert response.status_code == 401
    assert response.json() == {"detail": "unauthorized"}
    assert raw not in caplog.text
    assert raw not in response.text
    assert any(record.levelno == logging.WARNING for record in caplog.records)
    assert caplog.text.strip() != ""
