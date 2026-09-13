"""spec 0002 2.1, 2.4, 2.18: `RedisStatusNotifier` — `StatusNotifier` 포트의 Redis
Streams 구현. `aether:runs:status` 에 `StatusMessage` 의 필드를 문자열로 `XADD` 합니다.

값이 없는 선택 필드(`started_at`·`finished_at`·`failure_reason`·`trace_id`)는 필드
자체를 보내지 않습니다 — api 의 투영 소비자(P1-5b)가 "필드 없음" 과 "빈 문자열"을
구분할 필요가 없게 합니다.
"""

from __future__ import annotations

import redis
from redis.typing import EncodableT, FieldT

from aether_runtime.application.ports.outbound.status_notifier import StatusMessage

_DEFAULT_STREAM = "aether:runs:status"


class RedisStatusNotifier:
    """`StatusNotifier` 포트의 Redis Streams 구현(spec 0002 2.18)."""

    def __init__(self, client: redis.Redis, *, stream: str = _DEFAULT_STREAM) -> None:
        self._client = client
        self._stream = stream

    def notify(self, message: StatusMessage) -> None:
        # `redis-py` 의 `xadd` 시그니처는 `Dict[FieldT, EncodableT]`(불변 제네릭)를
        # 기대합니다 — `dict[str, str]` 로 지었다가 넘기면 mypy 가 불변성 때문에
        # 거부하므로, 처음부터 이 타입으로 짓습니다(값은 여전히 전부 `str`).
        fields: dict[FieldT, EncodableT] = {
            "run_id": str(message.run_id),
            "seq": str(message.seq),
            "status": message.status.value,
            "at": message.at.isoformat(),
        }
        if message.started_at is not None:
            fields["started_at"] = message.started_at.isoformat()
        if message.finished_at is not None:
            fields["finished_at"] = message.finished_at.isoformat()
        if message.failure_reason is not None:
            fields["failure_reason"] = message.failure_reason.value
        if message.trace_id is not None:
            fields["trace_id"] = message.trace_id
        self._client.xadd(self._stream, fields)
