"""루트 conftest — 공용 fixture 플러그인 등록과 `integration` 소켓 허용 (spec 0002 2.16, R-6, D-18).

`pytest_plugins` 는 **top-level(rootdir) conftest 에서만** 허용됩니다(pytest 9) — plan
0002 는 이 등록을 `apps/api/tests/conftest.py` 에 두는 것으로 적었지만, 그 파일은
top-level 이 아니므로 `Failed: Defining 'pytest_plugins' in a non-top-level conftest is
no longer supported` 로 수집 자체가 실패합니다(실측, 이 단위 보고의 "보고할 불일치").
그래서 `tests/support/pg.py` 의 fixture 는 여기서 한 번만 등록하고, `apps/api`·
`apps/worker`·`packages/runtime` 의 모든 테스트가 이 하나의 등록으로 공유합니다 —
fixture 는 요청될 때만 실행되므로 전역 등록이 다른 테스트에 부작용을 주지 않습니다.

`pyproject.toml` 의 `addopts` 가 `pytest-socket` 으로 기본 `--disable-socket`
(loopback 만 허용)을 켭니다 — `api-unit`(`not integration`)이 네트워크 없이 도는지
구조적으로 보장하기 위해서입니다(R-6). `integration` 마커가 붙은 테스트는
testcontainers 로 임의 포트의 실제 컨테이너에 접속하므로, 수집 시점에
`pytest.mark.enable_socket` 을 함께 붙여 그 테스트만 소켓 차단에서 빠지게 합니다.

`anyio_backend` fixture(spec 0002 2.16, P1-6): `@pytest.mark.anyio` 는 `anyio` 의
pytest 플러그인(FastAPI 의존이라 이미 설치됨, entry point 로 자동 등록 — 새 의존
없음)이 제공합니다. 기본은 `anyio_backend` 를 `["asyncio", "trio"]` 로 파라미터화해
같은 테스트를 두 백엔드로 두 번 돌리는데, 이 저장소는 `trio` 를 설치하지 않으므로
그대로 두면 모든 `anyio` 테스트가 `trio` 파라미터에서 `ModuleNotFoundError` 로
깨집니다(실측). `asyncio` 하나로 고정합니다.
"""

from __future__ import annotations

import pytest

pytest_plugins = ["tests.support.pg", "tests.support.redis"]


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    for item in items:
        if item.get_closest_marker("integration") is not None:
            item.add_marker(pytest.mark.enable_socket)
