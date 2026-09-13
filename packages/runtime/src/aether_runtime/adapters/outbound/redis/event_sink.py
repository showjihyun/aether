"""spec 0002 2.1, 2.7(개정 2): `RedisEventSink` — `EventSink` 포트의 Redis Streams 구현.

`aether:runs:{run_id}:events` 에 **explicit ID `<seq>-0`** 로 `XADD` 합니다 — `seq` 는
Run 안에서 1 부터 단조 증가하는 수열이라 스트림 ID 의 ms-seq 표기와 자연스럽게
겹칩니다. `MAXLEN ~ maxlen` (근사 트리밍, R-9 성능과 무관하게 정확한 카운트를
요구하지 않음)과, `run.finished` 뒤 `EXPIRE ttl_seconds` (Phase 1 은 이벤트를
영속하지 않습니다, 2.7 끝).

**같은 `seq` 재발행은 성공**입니다(2.4 의 재개, R-16) — Redis 는 스트림의 top ID
이하로 explicit `XADD` 하면 `ERR The ID specified in XADD is equal or smaller than
the target stream top item` 을 냅니다(redis-py 는 `ResponseError.args`/`str()` 에서
앞의 `ERR ` 코드를 떼어 냅니다 — 실측). 그 뒤에 남는 문자열만 흡수하고, 그 밖의
`ResponseError`(예: 그 키가 스트림이 아님)는 그대로 올립니다.
"""

from __future__ import annotations

from uuid import UUID

import redis
from redis.exceptions import ResponseError

from aether_runtime.domain.events import RunEvent

_DUPLICATE_ID_ERROR = "The ID specified in XADD is equal or smaller"
_DEFAULT_MAXLEN = 10_000
_DEFAULT_TTL_SECONDS = 86_400


class RedisEventSink:
    """`EventSink` 포트의 Redis Streams 구현(spec 0002 2.7)."""

    def __init__(
        self,
        client: redis.Redis,
        *,
        maxlen: int = _DEFAULT_MAXLEN,
        ttl_seconds: int = _DEFAULT_TTL_SECONDS,
    ) -> None:
        self._client = client
        self._maxlen = maxlen
        self._ttl_seconds = ttl_seconds

    def publish(self, event: RunEvent) -> None:
        stream = _stream_key(event.run_id)
        entry_id = f"{event.seq}-0"
        try:
            self._client.xadd(
                stream,
                {"data": event.model_dump_json()},
                id=entry_id,
                maxlen=self._maxlen,
                approximate=True,
            )
        except ResponseError as exc:
            if _DUPLICATE_ID_ERROR not in str(exc):
                raise
        if event.type == "run.finished":
            self._client.expire(stream, self._ttl_seconds)


def _stream_key(run_id: UUID) -> str:
    return f"aether:runs:{run_id}:events"
