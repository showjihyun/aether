"""spec 0002 2.4, 2.18, D-10 (P1-5a): `RequestedConsumer` — `aether:runs:requested`
소비자. 기존 `stream.py`(Phase 0, 읽기만 하고 처리하지 않음)의 후속입니다.

읽는 순서(2.4)는 **자기 PEL 먼저 → `XAUTOCLAIM` → `XREADGROUP(">")`** 입니다:

1. 재시작 시 `_drain_own_pel` 이 이 consumer 이름으로 이미 전달됐지만 ack 되지 않은
   메시지(예: 이전 프로세스가 처리 중 죽음)를 전부 비웁니다(`XREADGROUP … 0`).
2. 그 뒤 루프마다 `XAUTOCLAIM` 으로 다른 consumer 가 두고 간, `min_idle_ms` 이상
   유휴한 메시지를 먼저 가로챕니다(살아 있는 다른 worker 의 실행을 빼앗지 않도록
   기본값은 크게 잡습니다 — `Settings.worker_xautoclaim_min_idle_ms`).
3. 가로챌 것이 없으면 `XREADGROUP(">")` 으로 새 메시지를 블록 대기합니다.

세 경로 모두 **`count=1`** 입니다 — 한 번에 하나씩 처리해 `HandleRunRequested` 호출
사이 PEL 이 이 consumer 기준 최대 1건을 넘지 않습니다.

필드(`run_id`, `agent_version_id`)가 없거나 형식이 잘못된 메시지는 독약이므로
WARNING 로그와 함께 즉시 `XACK` 합니다 — handler 를 부르지 않습니다.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from threading import Event
from typing import Any, Protocol
from uuid import UUID

from redis import Redis
from redis.exceptions import ResponseError

from aether_worker.application.ports.inbound.handle_run_requested import (
    HandleRunRequested,
    RequestedMessage,
)

logger = logging.getLogger(__name__)

_BUSYGROUP = "BUSYGROUP"
_StreamEntry = tuple[str, Mapping[str, str]]


class _StreamClient(Protocol):
    """`RequestedConsumer` 가 실제로 쓰는 세 명령만 담은 구조적 타입 — 실제 `Redis`
    는 물론, 포트 계약 테스트의 계측용 프록시(`_CountSpy`)도 이 모양만 만족하면
    됩니다. `ensure_group` 은 `xgroup_create` 도 써야 하므로 여전히 `Redis` 를 받습니다.

    `streams`/`name`/`groupname`/`consumername`/`start_id` 는 `Any` 로 둡니다 —
    `redis-py` 의 실제 타입(`KeyT`/`StreamIdT`/`GroupT`/`ConsumerT`, 전부
    `bytes|str|memoryview|...` 유니온)까지 그대로 옮기면 이 포트 하나를 위해 벤더
    타입을 재수출하게 되어(AR-9 의 취지에 어긋남) 여기서는 실제로 쓰는 값의
    종류(문자열)만 호출부가 책임집니다.
    """

    def xreadgroup(
        self,
        groupname: str,
        consumername: str,
        streams: Any,
        count: int | None = None,
        block: int | None = None,
    ) -> Any: ...

    def xautoclaim(
        self,
        name: Any,
        groupname: Any,
        consumername: Any,
        min_idle_time: int,
        start_id: Any = "0-0",
        count: int | None = None,
    ) -> Any: ...

    def xack(self, name: Any, groupname: Any, *ids: Any) -> Any: ...


def ensure_group(client: Redis, stream: str, group: str) -> None:
    """`stream` 에 `group` consumer group 을 만듭니다(`XGROUP CREATE ... MKSTREAM`).

    스트림이 없으면 `mkstream=True` 가 빈 스트림을 함께 만듭니다. group 이 이미 있으면
    Redis 가 `BUSYGROUP` 오류를 내는데, 그것은 원하는 상태(멱등)이므로 무시합니다.
    """
    try:
        client.xgroup_create(name=stream, groupname=group, id="0", mkstream=True)
    except ResponseError as exc:
        if _BUSYGROUP not in str(exc):
            raise


class RequestedConsumer:
    """`aether:runs:requested` 소비자(spec 0002 2.4, 2.18)."""

    def __init__(
        self,
        client: _StreamClient,
        *,
        stream: str,
        group: str,
        consumer: str,
        handler: HandleRunRequested,
        xautoclaim_min_idle_ms: int,
        block_ms: int = 1000,
    ) -> None:
        self._client = client
        self._stream = stream
        self._group = group
        self._consumer = consumer
        self._handler = handler
        self._min_idle_ms = xautoclaim_min_idle_ms
        self._block_ms = block_ms

    def run_until(self, stop: Event) -> None:
        """`stop` 이 set 될 때까지 자기 PEL → XAUTOCLAIM → XREADGROUP(">") 순서로 돕니다."""
        self._drain_own_pel()
        while not stop.is_set():
            claimed = self._claim_one()
            if claimed is not None:
                self._handle(*claimed)
                continue
            fresh = self._read_one()
            if fresh is not None:
                self._handle(*fresh)

    # -- 읽기 경로 세 가지 --------------------------------------------------

    def _drain_own_pel(self) -> None:
        while True:
            response: Any = self._client.xreadgroup(
                groupname=self._group,
                consumername=self._consumer,
                streams={self._stream: "0"},
                count=1,
            )
            entries = _entries(response)
            if not entries:
                return
            self._handle(*entries[0])

    def _claim_one(self) -> _StreamEntry | None:
        result: Any = self._client.xautoclaim(
            name=self._stream,
            groupname=self._group,
            consumername=self._consumer,
            min_idle_time=self._min_idle_ms,
            start_id="0-0",
            count=1,
        )
        claimed = result[1]
        if not claimed:
            return None
        message_id, fields = claimed[0]
        return message_id, fields

    def _read_one(self) -> _StreamEntry | None:
        response: Any = self._client.xreadgroup(
            groupname=self._group,
            consumername=self._consumer,
            streams={self._stream: ">"},
            count=1,
            block=self._block_ms,
        )
        entries = _entries(response)
        if not entries:
            return None
        return entries[0]

    # -- 처리 -----------------------------------------------------------------

    def _handle(self, message_id: str, fields: Mapping[str, str]) -> None:
        message = _parse(message_id, fields)
        if message is None:
            logger.warning(
                "worker.requested_consumer.malformed_message",
                extra={"message_id": message_id, "fields": dict(fields)},
            )
            self._client.xack(self._stream, self._group, message_id)
            return

        outcome = self._handler(message)
        if outcome.ack:
            self._client.xack(self._stream, self._group, message_id)


def _entries(response: Any) -> list[_StreamEntry]:
    if not response:
        return []
    _stream_name, messages = response[0]
    return list(messages)


def _parse(message_id: str, fields: Mapping[str, str]) -> RequestedMessage | None:
    try:
        run_id = UUID(fields["run_id"])
        agent_version_id = UUID(fields["agent_version_id"])
    except (KeyError, ValueError):
        return None
    return RequestedMessage(
        message_id=message_id,
        run_id=run_id,
        agent_version_id=agent_version_id,
        traceparent=fields.get("traceparent"),
    )
