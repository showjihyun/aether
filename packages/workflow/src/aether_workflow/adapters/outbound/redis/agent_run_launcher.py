"""spec 0005 2.5 개정 3 (P4-2a B2): `RedisAgentRunLauncher` - `AgentRunLauncher` 포트의 Redis
Streams
구현. `aether:workflow:agent_runs:requested` 에 `XADD` 합니다.

필드 이름은 B1 이 세운 스트림 계약 그대로입니다(api 쪽 `WorkflowAgentRunRequest` 가 정본이고 서로
import 하지 않습니다, AR-7): `agent_run_id`·`agent_version_id`·`input`·`traceparent` 와 B2 가 더한
`requested_by`. `traceparent` 가 없으면 필드를 빼지 않고 빈 문자열을 싣습니다(`RedisRunNotifier` 와
같은 규칙). `XADD` 실패는 삼키지 않습니다 - 호출자의 메시지는 ack 되지 않고 같은 `agent_run_id` 로
다시 시도됩니다(api 쪽 선언이 멱등이라 자식 Run 은 하나입니다).
"""

from __future__ import annotations

import redis
from redis.typing import EncodableT, FieldT

from aether_workflow.application.ports.outbound.agent_run_launcher import AgentRunLaunch

_DEFAULT_STREAM = "aether:workflow:agent_runs:requested"


class RedisAgentRunLauncher:
    def __init__(self, client: redis.Redis, *, stream: str = _DEFAULT_STREAM) -> None:
        self._client = client
        self._stream = stream

    def launch(self, request: AgentRunLaunch) -> None:
        fields: dict[FieldT, EncodableT] = {
            "agent_run_id": str(request.agent_run_id),
            "agent_version_id": str(request.agent_version_id),
            "input": request.input,
            "requested_by": str(request.requested_by),
            "traceparent": request.traceparent or "",
        }
        self._client.xadd(self._stream, fields)
