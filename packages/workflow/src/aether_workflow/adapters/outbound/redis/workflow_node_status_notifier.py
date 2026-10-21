"""spec 0007 2.3 (P5-1): `RedisWorkflowNodeStatusNotifier` -- `WorkflowNodeStatusNotifier` 포트의
Redis Streams 구현. `aether:workflow_node_states:status` 에 필드를 문자열로 `XADD` 합니다.

값이 없는 선택 필드(`started_at`·`finished_at`·`failure_reason`)는 **필드 자체를 보내지
않습니다** - `RedisWorkflowStatusNotifier` 가 세운 계약과 같습니다. 노드 출력은 싣지 않습니다(D-4).
"""

from __future__ import annotations

import redis
from redis.typing import EncodableT, FieldT

from aether_workflow.application.ports.outbound.workflow_node_status_notifier import (
    WorkflowNodeStatusMessage,
)

_DEFAULT_STREAM = "aether:workflow_node_states:status"


class RedisWorkflowNodeStatusNotifier:
    def __init__(self, client: redis.Redis, *, stream: str = _DEFAULT_STREAM) -> None:
        self._client = client
        self._stream = stream

    def notify(self, message: WorkflowNodeStatusMessage) -> None:
        fields: dict[FieldT, EncodableT] = {
            "workflow_run_id": str(message.workflow_run_id),
            "node_id": message.node_id,
            "kind": message.kind.value,
            "status": message.status.value,
            "status_seq": str(message.status_seq),
        }
        if message.started_at is not None:
            fields["started_at"] = message.started_at.isoformat()
        if message.finished_at is not None:
            fields["finished_at"] = message.finished_at.isoformat()
        if message.failure_reason is not None:
            fields["failure_reason"] = message.failure_reason.value
        self._client.xadd(self._stream, fields)
