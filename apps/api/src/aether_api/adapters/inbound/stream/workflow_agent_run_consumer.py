"""spec 0005 2.5 개정 3 (P4-2a B1): `WorkflowAgentRunConsumer` —
`aether:workflow:agent_runs:requested`(worker → api) 소비자.

`workflow_run_status_consumer.py` 와 같은 모양입니다. consumer group `aether-api`. 읽는 순서는
자기 PEL 먼저(`XREADGROUP … 0`) → `XREADGROUP ">"`. 필드(계약의 정본은
`domain/workflow_agent_run_request.py`)를 `WorkflowAgentRunRequest` 로 파싱해
`DeclareWorkflowAgentRun` 을 부르고, 선언이 끝나면(새로 만들었든 이미 있었든) `XACK` 합니다.

- 파싱 실패는 독약 메시지입니다: WARNING 과 함께 즉시 ack, `declare` 는 부르지 않습니다.
- `declare` 가 예외를 던지면 **삼키지 않고 올리며 ack 하지 않습니다.** 없는 `agent_version_id`
  는 실행기가 이미 걸러 냅니다(plan 부록 A) — 여기서 FK 위반이 오면 그것은 평범한 입력이 아니라
  **버그**이므로 조용히 ack 하지 않습니다. 메시지는 PEL 에 남습니다.
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

from aether_api.application.ports.inbound.declare_workflow_agent_run import (
    DeclareWorkflowAgentRun,
)
from aether_api.domain.workflow_agent_run_request import WorkflowAgentRunRequest

logger = logging.getLogger(__name__)

_DEFAULT_STREAM = "aether:workflow:agent_runs:requested"
_DEFAULT_GROUP = "aether-api"
_StreamEntry = tuple[str, Mapping[str, str]]


def _default_consumer() -> str:
    return f"{socket.gethostname()}-{os.getpid()}"


def _parse(fields: Mapping[str, str]) -> WorkflowAgentRunRequest | None:
    try:
        return WorkflowAgentRunRequest.model_validate(dict(fields))
    except ValidationError:
        return None


def _entries(response: Any) -> list[_StreamEntry]:
    if not response:
        return []
    _stream_name, messages = response[0]
    return list(messages)


class WorkflowAgentRunConsumer:
    """`aether:workflow:agent_runs:requested` 소비자."""

    def __init__(
        self,
        client: Redis,
        declare: DeclareWorkflowAgentRun,
        *,
        stream: str = _DEFAULT_STREAM,
        group: str = _DEFAULT_GROUP,
        consumer: str | None = None,
        block_ms: int = 1000,
    ) -> None:
        self._client = client
        self._declare = declare
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
                "workflow_agent_run_consumer.malformed_message",
                extra={"message_id": message_id, "fields": dict(fields)},
            )
            self._client.xack(self.stream, self.group, message_id)
            return

        self._declare(message)  # 예외는 올립니다 -- ack 하지 않고 PEL 에 남깁니다
        self._client.xack(self.stream, self.group, message_id)  # 반환값 무관 (멱등 무시)
