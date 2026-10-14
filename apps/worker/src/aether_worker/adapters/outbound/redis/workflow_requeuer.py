"""spec 0005 2.5 개정 3 (P4-2a B2): `RedisWorkflowRequeuer` - `WorkflowRequeuer` 의 Redis Streams
구현.
`aether:workflow_runs:requested` 에 api 가 쓰는 것과 **같은 계약**(`workflow_run_id`·
`workflow_version_id`·`traceparent`)으로 `XADD` 합니다. `traceparent` 는 빈 문자열 - 재큐는 새
요청 span 이 없습니다(api 의 `RedisWorkflowRunNotifier` 도 없을 때 빈 문자열을 싣습니다).
"""

from __future__ import annotations

from redis import Redis
from redis.typing import EncodableT, FieldT

from aether_worker.application.ports.outbound.parked_workflow_finder import ParkedWorkflow


class RedisWorkflowRequeuer:
    def __init__(self, client: Redis, *, stream: str = "aether:workflow_runs:requested") -> None:
        self._client = client
        self._stream = stream

    def requeue(self, workflow: ParkedWorkflow) -> None:
        fields: dict[FieldT, EncodableT] = {
            "workflow_run_id": str(workflow.workflow_run_id),
            "workflow_version_id": str(workflow.workflow_version_id),
            "traceparent": "",
        }
        self._client.xadd(self._stream, fields)
