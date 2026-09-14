"""spec 0002 2.4, 2.18, D-2 (P1-5b): `StatusConsumer` — `aether:runs:status` 소비자.

consumer group `aether-api`(2.4 투영 문단). 읽는 순서는 자기 PEL 먼저(`XREADGROUP … 0`,
재시작 시 이전 프로세스가 처리 중 죽어 ack 못한 메시지를 비웁니다) → `XREADGROUP ">"`
로 새 메시지. worker 의 `RequestedConsumer`(`apps/worker/.../requested_consumer.py`)와
달리 `XAUTOCLAIM` 은 없습니다 — 투영 메시지는 순서가 섞여도(`seq` 로 멱등, D-2) 결과가
같아서 다른 consumer 가 두고 간 메시지를 적극적으로 가로챌 이유가 없고, api 인스턴스는
Phase 1 에서 하나뿐입니다(2.4).

필드를 `RunStatusMessage` 로 파싱해 `ApplyRunStatus` 를 부르고, 적용 여부(`True`/
`False`)와 무관하게(멱등 무시) `XACK` 합니다 — `apply` 호출이 돌아온 시점에는 이미
DB 커밋이 끝나 있습니다(유스케이스 → 저장소가 `with connect() as conn:` 블록 안에서
커밋). 파싱 실패(필드 누락·형식 오류)는 독약 메시지이므로 WARNING 로그와 함께 즉시
ack 합니다 — `apply` 를 부르지 않습니다.
"""

from __future__ import annotations

import logging
import os
import socket
from collections.abc import Mapping
from threading import Event
from typing import Any

from pydantic import ValidationError
from redis import Redis
from redis.exceptions import ResponseError

from aether_api.application.ports.inbound.apply_run_status import ApplyRunStatus
from aether_api.domain.run_status_message import RunStatusMessage

logger = logging.getLogger(__name__)

_DEFAULT_STREAM = "aether:runs:status"
_DEFAULT_GROUP = "aether-api"
_BUSYGROUP = "BUSYGROUP"
_StreamEntry = tuple[str, Mapping[str, str]]


def _default_consumer() -> str:
    return f"{socket.gethostname()}-{os.getpid()}"


def ensure_group(client: Redis, stream: str, group: str) -> None:
    """`stream` 에 `group` consumer group 을 만듭니다(`XGROUP CREATE ... MKSTREAM`).

    이미 있으면(`BUSYGROUP`) 원하는 상태(멱등)이므로 무시합니다 — worker
    `requested_consumer.ensure_group` 과 같은 패턴(별개 구현, api 는 worker 를
    import 하지 않습니다, AR-7).
    """
    try:
        client.xgroup_create(name=stream, groupname=group, id="0", mkstream=True)
    except ResponseError as exc:
        if _BUSYGROUP not in str(exc):
            raise


def _parse(fields: Mapping[str, str]) -> RunStatusMessage | None:
    try:
        return RunStatusMessage.model_validate(dict(fields))
    except ValidationError:
        return None


def _entries(response: Any) -> list[_StreamEntry]:
    if not response:
        return []
    _stream_name, messages = response[0]
    return list(messages)


class StatusConsumer:
    """`aether:runs:status` 소비자(spec 0002 2.4, 2.18, D-2)."""

    def __init__(
        self,
        client: Redis,
        apply: ApplyRunStatus,
        *,
        stream: str = _DEFAULT_STREAM,
        group: str = _DEFAULT_GROUP,
        consumer: str | None = None,
        block_ms: int = 1000,
    ) -> None:
        self._client = client
        self._apply = apply
        self._stream = stream
        self._group = group
        self._consumer = consumer if consumer is not None else _default_consumer()
        self._block_ms = block_ms

    def run_until(self, stop: Event) -> None:
        """`stop` 이 set 될 때까지 자기 PEL → `XREADGROUP(">")` 순서로 돕니다."""
        self._drain_own_pel()
        while not stop.is_set():
            entry = self._read_one()
            if entry is not None:
                self._handle(*entry)

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

    def _handle(self, message_id: str, fields: Mapping[str, str]) -> None:
        message = _parse(fields)
        if message is None:
            logger.warning(
                "status_consumer.malformed_message",
                extra={"message_id": message_id, "fields": dict(fields)},
            )
            self._client.xack(self._stream, self._group, message_id)
            return

        self._apply(message)  # 반환값과 무관하게 ack (D-2, 멱등 무시)
        self._client.xack(self._stream, self._group, message_id)
