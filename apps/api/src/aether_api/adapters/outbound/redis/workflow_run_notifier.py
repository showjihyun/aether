"""spec 0005 2.9 개정 2, plan 부록 A: `RedisWorkflowRunNotifier` — `WorkflowRunNotifier` 포트의
Redis Streams 구현. `aether:workflow_runs:requested` 에 `workflow_run_id`·`workflow_version_id`·
`traceparent` 를 `XADD` 합니다. Agent Run 의 `aether:runs:requested` 와 **다른 스트림**입니다.

`traceparent` 가 `None` 이면 빈 문자열로 채웁니다 — 스트림 계약의 세 필드를 항상 싣습니다
(`run_notifier.py` 와 같은 규칙).
"""

from __future__ import annotations

from uuid import UUID

import redis

_DEFAULT_STREAM = "aether:workflow_runs:requested"


class RedisWorkflowRunNotifier:
    """`WorkflowRunNotifier` 포트의 Redis Streams 구현."""

    def __init__(self, client: redis.Redis, *, stream: str = _DEFAULT_STREAM) -> None:
        self._client = client
        self._stream = stream

    def requested(
        self, workflow_run_id: UUID, workflow_version_id: UUID, traceparent: str | None
    ) -> None:
        self._client.xadd(
            self._stream,
            {
                "workflow_run_id": str(workflow_run_id),
                "workflow_version_id": str(workflow_version_id),
                "traceparent": traceparent if traceparent is not None else "",
            },
        )
