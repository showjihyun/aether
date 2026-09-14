"""spec 0002 2.2, 2.18: `RedisRunNotifier` — `RunNotifier` 포트의 Redis Streams 구현.
`aether:runs:requested` 에 `run_id`·`agent_version_id`·`traceparent` 를 `XADD` 합니다.

worker 의 `_parse`(`apps/worker/.../requested_consumer.py`)는 `traceparent` 를
`fields.get("traceparent")` 로 읽어 필드가 없어도(`None`) 파싱에 실패하지 않습니다 —
그래도 이 어댑터는 스트림 계약(2.18)이 나열한 세 필드를 항상 실어 보냅니다:
`traceparent` 가 `None` 이면(P1-8 이전, api 는 아직 트레이싱이 없음) 빈 문자열로
채웁니다. P1-8 이 실제 `traceparent` 값을 채웁니다.
"""

from __future__ import annotations

from uuid import UUID

import redis

_DEFAULT_STREAM = "aether:runs:requested"


class RedisRunNotifier:
    """`RunNotifier` 포트의 Redis Streams 구현(spec 0002 2.18)."""

    def __init__(self, client: redis.Redis, *, stream: str = _DEFAULT_STREAM) -> None:
        self._client = client
        self._stream = stream

    def requested(self, run_id: UUID, agent_version_id: UUID, traceparent: str | None) -> None:
        self._client.xadd(
            self._stream,
            {
                "run_id": str(run_id),
                "agent_version_id": str(agent_version_id),
                "traceparent": traceparent if traceparent is not None else "",
            },
        )
