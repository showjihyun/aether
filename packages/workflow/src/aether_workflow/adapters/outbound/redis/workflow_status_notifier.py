"""spec 0005 2.9 개정 2: `RedisWorkflowStatusNotifier` - `WorkflowStatusNotifier` 포트의 Redis
Streams 구현. `aether:workflow_runs:status` 에 `WorkflowStatusMessage` 의 필드를 문자열로
`XADD` 합니다.

값이 없는 선택
필드(`current_node_id`·`waiting_run_id`·`started_at`·`finished_at`·`failure_reason`)는 **필드
자체를 보내지 않습니다** - api 의 투영 소비자(`WorkflowRunStatusConsumer`)가 "필드 없음" 과
"빈 문자열" 을 구분할 필요가 없게 합니다(A1 이 세운 계약).
"""

from __future__ import annotations

import redis
from redis.typing import EncodableT, FieldT

from aether_workflow.application.ports.outbound.workflow_status_notifier import (
    WorkflowStatusMessage,
)

_DEFAULT_STREAM = "aether:workflow_runs:status"


class RedisWorkflowStatusNotifier:
    def __init__(self, client: redis.Redis, *, stream: str = _DEFAULT_STREAM) -> None:
        self._client = client
        self._stream = stream

    def notify(self, message: WorkflowStatusMessage) -> None:
        fields: dict[FieldT, EncodableT] = {
            "workflow_run_id": str(message.workflow_run_id),
            "seq": str(message.seq),
            "status": message.status.value,
            "at": message.at.isoformat(),
        }
        if message.current_node_id is not None:
            fields["current_node_id"] = message.current_node_id
        if message.waiting_run_id is not None:
            fields["waiting_run_id"] = str(message.waiting_run_id)
        if message.started_at is not None:
            fields["started_at"] = message.started_at.isoformat()
        if message.finished_at is not None:
            fields["finished_at"] = message.finished_at.isoformat()
        if message.failure_reason is not None:
            fields["failure_reason"] = message.failure_reason.value
        self._client.xadd(self._stream, fields)
