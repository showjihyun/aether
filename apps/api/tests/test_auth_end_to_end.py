"""spec 0001 R-9 · 2.9 H-3: 조립 전체 — `create_app` 이 PostgreSQL 로 지연 조립한
`app.state.authenticate` 로 실제 발급된 키를 인증하고, `revoke` 뒤에는 거부합니다.

`packages/sdk`/`/healthz` 외의 제품 보호 경로는 아직 없으므로(Phase 1 의 `POST /agents`
가 처음), 이 테스트도 `test_auth_http.py` 와 같이 테스트 전용 라우트를 답니다.

`test_auth_http.py` 와 같은 이유로 `from __future__ import annotations` 을 쓰지
않습니다 — 로컬 변수 `dependency` 를 라우트 파라미터의 애노테이션으로 쓰는데, 지연
문자열 애노테이션(PEP 563)이면 FastAPI 가 그 이름을 모듈 전역에서 찾지 못해 422 가
납니다.
"""

from collections.abc import Callable
from typing import Annotated

import psycopg
import pytest
from aether_api.adapters.inbound.http.auth import require_principal
from aether_api.adapters.outbound.db.api_keys import PostgresApiKeyStore
from aether_api.application.usecases.issue_api_key import IssueApiKeyUseCase
from aether_api.domain.api_key import Principal
from aether_api.main import create_app
from aether_api.settings import Settings
from fastapi import Depends
from fastapi.testclient import TestClient

pytestmark = pytest.mark.integration


def test_authenticate_end_to_end_issue_then_revoke(
    control_database_url: str,
    control_connection_factory: Callable[[], psycopg.Connection],
) -> None:
    settings = Settings(database_url=control_database_url)
    app = create_app(settings)
    assert hasattr(app.state, "authenticate")

    dependency = Annotated[Principal, Depends(require_principal(app.state.authenticate))]

    @app.get("/_test/e2e-protected")
    def _protected(principal: dependency) -> dict[str, str]:
        return {"label": principal.label}

    store = PostgresApiKeyStore(control_connection_factory)
    issued = IssueApiKeyUseCase(store)("e2e")
    client = TestClient(app)

    ok_response = client.get(
        "/_test/e2e-protected", headers={"Authorization": f"Bearer {issued.raw_key}"}
    )
    assert ok_response.status_code == 200
    assert ok_response.json() == {"label": "e2e"}

    store.revoke(issued.key.id)

    revoked_response = client.get(
        "/_test/e2e-protected", headers={"Authorization": f"Bearer {issued.raw_key}"}
    )
    assert revoked_response.status_code == 401
