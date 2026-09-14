"""`integration` 마커 통합 테스트 공통 Redis fixture (spec 0002 2.16, P1-5a).

`apps/worker/tests/test_connect.py` 가 원래 로컬에서 정의했던 `redis_container` 를
여기로 옮겨 `apps/worker`·`packages/runtime` 의 테스트가 함께 씁니다 —
`tests/support/pg.py` 와 같은 이유(spec 0002 P1-2a)입니다. 등록은 루트 `conftest.py`
의 `pytest_plugins` 에 `"tests.support.redis"` 를 더해 한 곳에서만 합니다.

컨테이너는 세션당 하나(`scope="session"`)이지만, 여러 테스트 파일이 같은 스트림
이름(예: `aether:runs:requested`, `aether:runs:status`)을 쓰므로 `redis_url`/
`redis_client` 는 **함수 스코프**로 매번 `FLUSHDB` 해 테스트 사이의 상태를 지웁니다 —
`tests/support/pg.py` 의 세션 스코프 DB와 달리 Redis 는 스트림 키 이름이 고정이라
격리가 없으면 테스트끼리 서로의 메시지를 봅니다.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from redis import Redis
from testcontainers.community.redis import RedisContainer


@pytest.fixture(scope="session")
def redis_container() -> Iterator[RedisContainer]:
    with RedisContainer("redis:7-alpine") as container:
        yield container


@pytest.fixture
def redis_url(redis_container: RedisContainer) -> Iterator[str]:
    """컨테이너의 접속 URL. 매 테스트 시작 전에 `FLUSHDB` 로 상태를 지웁니다."""
    host = redis_container.get_container_host_ip()
    port = redis_container.get_exposed_port(6379)
    url = f"redis://{host}:{port}/0"
    client: Redis = Redis.from_url(url, decode_responses=True)
    try:
        client.flushdb()
        yield url
    finally:
        client.close()


@pytest.fixture
def redis_client(redis_url: str) -> Iterator[Redis]:
    """`redis_url` 위의 접속 클라이언트 하나. `redis_url` 이 이미 `FLUSHDB` 했습니다."""
    client: Redis = Redis.from_url(redis_url, decode_responses=True)
    try:
        yield client
    finally:
        client.close()
