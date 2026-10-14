"""spec 0005 2.9 개정 2, 2.10 (P4-2a A1): `WorkflowRunStatusConsumer` —
`aether:workflow_runs:status` 소비자.

`status_consumer.py` 와 같은 모양입니다. consumer group `aether-api`. 읽는 순서는 자기 PEL
먼저(`XREADGROUP … 0`) → `XREADGROUP ">"` 로 새 메시지. `XAUTOCLAIM` 은 없습니다 — 투영
메시지는 순서가 섞여도(`seq` 로 멱등) 결과가 같고 api 인스턴스는 이 단계에서 하나뿐입니다.

필드를 `WorkflowRunStatusMessage` 로 파싱해 `ApplyWorkflowRunStatus` 를 부르고, 적용 여부와
무관하게 `XACK` 합니다. 파싱 실패는 독약 메시지이므로 WARNING 과 함께 즉시 ack 하고 `apply` 는
부르지 않습니다.
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

from aether_api.application.ports.inbound.workflow_runs import ApplyWorkflowRunStatus
from aether_api.domain.workflow_run_status_message import WorkflowRunStatusMessage

logger = logging.getLogger(__name__)

_DEFAULT_STREAM = "aether:workflow_runs:status"
_DEFAULT_GROUP = "aether-api"
_StreamEntry = tuple[str, Mapping[str, str]]


def _default_consumer() -> str:
    return f"{socket.gethostname()}-{os.getpid()}"


def _parse(fields: Mapping[str, str]) -> WorkflowRunStatusMessage | None:
    try:
        return WorkflowRunStatusMessage.model_validate(dict(fields))
    except ValidationError:
        return None


def _entries(response: Any) -> list[_StreamEntry]:
    if not response:
        return []
    _stream_name, messages = response[0]
    return list(messages)


class WorkflowRunStatusConsumer:
    """`aether:workflow_runs:status` 소비자."""

    def __init__(
        self,
        client: Redis,
        apply: ApplyWorkflowRunStatus,
        *,
        stream: str = _DEFAULT_STREAM,
        group: str = _DEFAULT_GROUP,
        consumer: str | None = None,
        block_ms: int = 1000,
    ) -> None:
        self._client = client
        self._apply = apply
        self.stream = stream
        self.group = group
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
                groupname=self.group,
                consumername=self._consumer,
                streams={self.stream: "0"},
                count=1,
            )
            entries = _entries(response)
            if not entries:
                return
            self._handle(*entries[0])

    def _read_one(self) -> _StreamEntry | None:
        response: Any = self._client.xreadgroup(
            groupname=self.group,
            consumername=self._consumer,
            streams={self.stream: ">"},
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
                "workflow_run_status_consumer.malformed_message",
                extra={"message_id": message_id, "fields": dict(fields)},
            )
            self._client.xack(self.stream, self.group, message_id)
            return

        self._apply(message)  # 반환값과 무관하게 ack (멱등 무시)
        self._client.xack(self.stream, self.group, message_id)
