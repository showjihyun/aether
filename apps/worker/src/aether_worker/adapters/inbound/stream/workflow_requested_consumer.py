"""spec 0005 2.9 개정 2 (P4-2a A): `WorkflowRequestedConsumer` - `aether:workflow_runs:requested`
소비자(`RequestedConsumer` 와 같은 모양, spec 0002 2.4, D-10).

읽는 순서는 **자기 PEL 먼저 -> `XAUTOCLAIM` -> `XREADGROUP(">")`** 이고 세 경로 모두 `count=1`
입니다 - 재시작 복구, 다른 worker 가 두고 간 메시지 가로채기, 새 메시지 순입니다.

필드(`workflow_run_id`, `workflow_version_id`)가 없거나 형식이 잘못된 메시지는 독약이므로 WARNING
로그와 함께 즉시 `XACK` 하고 handler 를 부르지 않습니다. `traceparent` 는 없거나 빈 문자열이면
`None` 입니다.

`ensure_group` 은 Agent Run 소비자의 것을 재사용합니다(스트림·그룹 이름만 다릅니다).
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from threading import Event
from typing import Any, Protocol
from uuid import UUID

from aether_worker.application.ports.inbound.handle_workflow_requested import (
    HandleWorkflowRequested,
    WorkflowRequestedMessage,
)

logger = logging.getLogger(__name__)

_StreamEntry = tuple[str, Mapping[str, str]]


class _StreamClient(Protocol):
    """소비자가 실제로 쓰는 세 명령만 담은 구조적 타입 - 실제 `Redis` 도, 계약 테스트의 계측용
    프록시도 이 모양만 만족하면 됩니다(`RequestedConsumer` 와 같은 이유)."""

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


class WorkflowRequestedConsumer:
    def __init__(
        self,
        client: _StreamClient,
        *,
        stream: str,
        group: str,
        consumer: str,
        handler: HandleWorkflowRequested,
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
        """`stop` 이 set 될 때까지 자기 PEL -> XAUTOCLAIM -> XREADGROUP(">") 순서로 돕니다."""
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
                "worker.workflow_requested_consumer.malformed_message",
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


def _parse(message_id: str, fields: Mapping[str, str]) -> WorkflowRequestedMessage | None:
    try:
        workflow_run_id = UUID(fields["workflow_run_id"])
        workflow_version_id = UUID(fields["workflow_version_id"])
    except (KeyError, ValueError):
        return None
    return WorkflowRequestedMessage(
        message_id=message_id,
        workflow_run_id=workflow_run_id,
        workflow_version_id=workflow_version_id,
        traceparent=fields.get("traceparent") or None,
    )
