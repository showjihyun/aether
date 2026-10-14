"""spec 0005 2.10, D-13: `RedisWorkflowEventSink` - `WorkflowEventSink` 포트의 Redis Streams 구현.

`aether:workflow_runs:{id}:events` 에 **explicit ID `<seq>-0`** 로 `XADD` 합니다(`RedisEventSink`
와 같은 모양, 다른 키). `MAXLEN ~ maxlen` 과 `workflow.finished` 뒤 `EXPIRE ttl_seconds`.

**같은 `seq` 재발행은 성공**입니다 - Redis 는 스트림의 top ID 이하로 explicit `XADD` 하면
`The ID specified in XADD is equal or smaller than the target stream top item` 을 냅니다. 그 뒤에
남는 문자열만 흡수하고, 그 밖의 `ResponseError`(예: 그 키가 스트림이 아님)는 그대로 올립니다.
"""

from __future__ import annotations

from uuid import UUID

import redis
from redis.exceptions import ResponseError

from aether_workflow.domain.events import WorkflowEvent

_DUPLICATE_ID_ERROR = "The ID specified in XADD is equal or smaller"
_DEFAULT_MAXLEN = 10_000
_DEFAULT_TTL_SECONDS = 86_400


class RedisWorkflowEventSink:
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

    def publish(self, event: WorkflowEvent) -> None:
        stream = _stream_key(event.workflow_run_id)
        try:
            self._client.xadd(
                stream,
                {"data": event.model_dump_json()},
                id=f"{event.seq}-0",
                maxlen=self._maxlen,
                approximate=True,
            )
        except ResponseError as exc:
            if _DUPLICATE_ID_ERROR not in str(exc):
                raise
        if event.type == "workflow.finished":
            self._client.expire(stream, self._ttl_seconds)


def _stream_key(workflow_run_id: UUID) -> str:
    return f"aether:workflow_runs:{workflow_run_id}:events"
