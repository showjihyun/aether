"""spec 0004 2.4, D-4: `IngestionStatusConsumer` — `aether:knowledge:ingestions:status`
소비자(`StatusConsumer` 와 같은 모양, spec 0002 2.4, 2.18, D-2).

consumer group `aether-api`. 읽는 순서는 자기 PEL 먼저 → `XREADGROUP(">")`. 필드를
`KnowledgeIngestionStatusMessage` 로 파싱해 `ApplyIngestionStatus` 를 부르고, 적용
여부와 무관하게 `XACK` 합니다(D-2 와 같은 멱등 취급). 파싱 실패는 독약 메시지이므로
WARNING 로그와 함께 즉시 ack 합니다.
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

from aether_api.application.ports.inbound.apply_ingestion_status import ApplyIngestionStatus
from aether_api.domain.knowledge_ingestion_status_message import KnowledgeIngestionStatusMessage

logger = logging.getLogger(__name__)

_DEFAULT_STREAM = "aether:knowledge:ingestions:status"
_DEFAULT_GROUP = "aether-api"
_BUSYGROUP = "BUSYGROUP"
_StreamEntry = tuple[str, Mapping[str, str]]


def _default_consumer() -> str:
    return f"{socket.gethostname()}-{os.getpid()}"


def ensure_group(client: Redis, stream: str, group: str) -> None:
    try:
        client.xgroup_create(name=stream, groupname=group, id="0", mkstream=True)
    except ResponseError as exc:
        if _BUSYGROUP not in str(exc):
            raise


def _parse(fields: Mapping[str, str]) -> KnowledgeIngestionStatusMessage | None:
    try:
        return KnowledgeIngestionStatusMessage.model_validate(dict(fields))
    except ValidationError:
        return None


def _entries(response: Any) -> list[_StreamEntry]:
    if not response:
        return []
    _stream_name, messages = response[0]
    return list(messages)


class IngestionStatusConsumer:
    """`aether:knowledge:ingestions:status` 소비자(spec 0004 2.4, D-4)."""

    def __init__(
        self,
        client: Redis,
        apply: ApplyIngestionStatus,
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
                "ingestion_status_consumer.malformed_message",
                extra={"message_id": message_id, "fields": dict(fields)},
            )
            self._client.xack(self._stream, self._group, message_id)
            return

        self._apply(message)
        self._client.xack(self._stream, self._group, message_id)
