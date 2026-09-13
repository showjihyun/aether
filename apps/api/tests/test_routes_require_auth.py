"""spec 0002 R-8, DP-6: 새 경로는 전부 인증 뒤에 있습니다 — 헤더 없는 요청은 401.

`app.routes` 를 순회해 예외 목록(`/healthz`, 문서 경로) 밖의 모든 `APIRoute` 에 헤더
없는 요청을 보냅니다. FastAPI 0.141 은 `include_router` 로 등록된 라우트를
`fastapi.routing._IncludedRouter` 로 감싸 지연 평가하므로(세션에서 확인 — plan/spec
이 가정한 "`app.routes` 를 바로 순회" 로는 `APIRoute` 가 보이지 않습니다), 실제
`APIRoute` 를 찾으려면 `_IncludedRouter.original_router.routes` 를 재귀적으로
내려가야 합니다.
"""

from __future__ import annotations

from uuid import uuid4

from aether_api.domain.api_key import Principal, Unauthenticated
from aether_api.main import create_app
from aether_api.settings import Settings
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from starlette.routing import BaseRoute

_EXEMPT_PATHS = {"/healthz", "/openapi.json", "/docs", "/docs/oauth2-redirect", "/redoc"}


class _AlwaysUnauthenticated:
    """`Authenticate` 포트의 fake — 어떤 키도 통과시키지 않습니다."""

    def __call__(self, raw_key: str | None) -> Principal:
        raise Unauthenticated("always")


def _iter_api_routes(routes: list[BaseRoute]) -> list[APIRoute]:
    """`_IncludedRouter` 를 재귀적으로 펼쳐 실제 `APIRoute` 만 모읍니다."""
    found: list[APIRoute] = []
    for route in routes:
        if isinstance(route, APIRoute):
            found.append(route)
            continue
        original_router = getattr(route, "original_router", None)
        if original_router is not None:
            found.extend(_iter_api_routes(original_router.routes))
    return found


def _fill_path_params(path: str) -> str:
    return path.replace("{agent_id}", str(uuid4())).replace("{version}", "1")


def test_every_protected_route_returns_401_without_credentials() -> None:
    app = create_app(Settings(), authenticate=_AlwaysUnauthenticated())
    client = TestClient(app)

    api_routes = [r for r in _iter_api_routes(app.routes) if r.path not in _EXEMPT_PATHS]
    assert api_routes, "no APIRoute found to check — route discovery may be broken"

    checked = 0
    for route in api_routes:
        path = _fill_path_params(route.path)
        for method in route.methods or set():
            if method == "HEAD":
                continue
            response = client.request(method, path)
            assert response.status_code == 401, f"{method} {path} -> {response.status_code}"
            checked += 1

    assert checked > 0


def test_agents_router_is_registered_with_real_api_routes() -> None:
    """자기 증명 — `/agents` 경로가 실제로 `APIRoute` 로(발견 로직이 헛돌지 않고) 등록됩니다."""
    app = create_app(Settings(), authenticate=_AlwaysUnauthenticated())
    api_routes = _iter_api_routes(app.routes)
    agent_paths = {r.path for r in api_routes}

    assert "/agents" in agent_paths
    assert "/agents/{agent_id}" in agent_paths
    assert "/agents/{agent_id}/versions/{version}" in agent_paths
